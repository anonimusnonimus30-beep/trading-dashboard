#!/usr/bin/env python3
"""
Analyzer de rendimiento: descarga fills reales de Alpaca (actividades
FILL, no orders) y calcula P&L realizado por símbolo usando FIFO.
"""

import os
import json
from collections import deque
from pathlib import Path
import requests


def safe_float(value, default=0.0):
    """Convierte valor a float de forma segura"""
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


# Umbral de "polvo": por debajo de esto una operacion no mueve la aguja
# pero pesa lo mismo en el porcentaje de acierto. Sale de los datos, no de
# una corazonada: es el corte donde el aporte al P&L se vuelve nulo.
DUST_NOTIONAL_USD = 250.0


class PerformanceAnalyzer:
    def __init__(self):
        self.account1_key = os.getenv("APCA_API_KEY_ID")
        self.account1_secret = os.getenv("APCA_API_SECRET_KEY")
        self.account1_url = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")

        self.account2_key = os.getenv("SPY_APCA_API_KEY")
        self.account2_secret = os.getenv("SPY_APCA_API_SECRET")
        self.account2_url = os.getenv("SPY_APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

        self.results = {}

    def _get_headers(self, key, secret):
        return {
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
        }

    def _get_fill_activities(self, key, secret, base_url):
        """Obtiene TODAS las actividades de tipo FILL (fills reales, no orders).

        Nota: /v2/orders NO sirve para esto porque cada order representa un
        solo lado (buy o sell) y su identificador es "id", no "order_id".
        Las actividades FILL sí traen qty/price/side reales de cada ejecución.
        """
        headers = self._get_headers(key, secret)
        url = f"{base_url}/v2/account/activities"
        all_fills = []
        page_token = None

        try:
            while True:
                params = {
                    "activity_types": "FILL",
                    "direction": "asc",
                    "page_size": 100,
                }
                if page_token:
                    params["page_token"] = page_token

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=20,
                )
                response.raise_for_status()
                page = response.json() if response.ok else []

                if not page:
                    break

                all_fills.extend(page)

                if len(page) < 100:
                    break

                new_token = page[-1].get("id")
                if not new_token or new_token == page_token:
                    break
                page_token = new_token

                print(f"  📄 Paginando... ({len(all_fills)} fills obtenidos hasta ahora)")

            print(f"  ✅ Total de fills históricos: {len(all_fills)}")
            return all_fills
        except Exception as e:
            print(f"⚠️ Error obteniendo fills: {e}")
            return []

    def analyze_symbol(self, fills, symbol):
        """Calcula P&L realizado por símbolo emparejando compras/ventas por FIFO"""
        symbol_fills = [f for f in fills if f.get("symbol") == symbol]

        if not symbol_fills:
            return None

        symbol_fills.sort(key=lambda f: f.get("transaction_time", ""))

        lots = deque()  # lotes de compra abiertos: [qty, price]
        realized_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        trades = []

        for fill in symbol_fills:
            side = str(fill.get("side", "")).lower()
            qty = safe_float(fill.get("qty"))
            price = safe_float(fill.get("price"))

            if qty <= 0:
                continue

            if side == "buy":
                lots.append([qty, price])
                continue

            if side != "sell":
                continue

            remaining = qty
            cost_basis = 0.0
            matched_qty = 0.0

            while remaining > 0 and lots:
                lot_qty, lot_price = lots[0]
                matched = min(remaining, lot_qty)

                cost_basis += matched * lot_price
                remaining -= matched
                matched_qty += matched
                lot_qty -= matched

                if lot_qty <= 1e-9:
                    lots.popleft()
                else:
                    lots[0][0] = lot_qty

            if matched_qty <= 0:
                # Venta sin lote de compra previo (posición heredada/transferida)
                continue

            proceeds = matched_qty * price
            pnl = proceeds - cost_basis
            avg_buy = cost_basis / matched_qty
            realized_pnl += pnl

            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1

            trades.append({
                "order_id": str(fill.get("order_id") or fill.get("id") or "unknown")[:8],
                "date": str(fill.get("transaction_time", ""))[:10],
                "buy_price": round(avg_buy, 2),
                "sell_price": round(price, 2),
                "qty": round(matched_qty, 4),
                "notional": round(cost_basis, 2),
                "pnl": round(pnl, 2),
            })

        # Una venta se empareja contra VARIOS lotes de compra (FIFO), y
        # cada emparejamiento generaba una fila. Eso inflaba el recuento
        # entre 1,1x y 5x segun el bot: ARKK figuraba con 18 operaciones
        # siendo 8 ordenes, USMV con 10 siendo 2. Peor aun, partia una
        # orden real de $1.300 en 4 pedazos de ~$325 y varios caian por
        # debajo del umbral de "polvo", contaminando esa metrica tambien.
        # Se agrupa por order_id: una orden = una decision = una fila.
        ordenes = {}
        for t in trades:
            o = ordenes.setdefault(t["order_id"], {
                "order_id": t["order_id"], "date": t["date"],
                "qty": 0.0, "notional": 0.0, "pnl": 0.0,
                "_proceeds": 0.0,
            })
            o["qty"] += t["qty"]
            o["notional"] += t["notional"]
            o["pnl"] += t["pnl"]
            o["_proceeds"] += t["sell_price"] * t["qty"]

        operaciones = []
        for o in ordenes.values():
            q = o["qty"]
            operaciones.append({
                "order_id": o["order_id"],
                "date": o["date"],
                # precio medio ponderado de los lotes que se cerraron
                "buy_price": round(o["notional"] / q, 2) if q else 0,
                "sell_price": round(o["_proceeds"] / q, 2) if q else 0,
                "qty": round(q, 4),
                "notional": round(o["notional"], 2),
                "pnl": round(o["pnl"], 2),
            })
        operaciones.sort(key=lambda t: t["date"])

        winning_trades = sum(1 for t in operaciones if t["pnl"] > 0)
        losing_trades = sum(1 for t in operaciones if t["pnl"] < 0)
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # El win rate sobre TODAS las ordenes sigue enganiando un poco: los
        # rebalanceos dejan ordenes minusculas (el minimo del bot son $5)
        # que mueven centavos y pesan igual que una de $3.000 en el
        # porcentaje. Se reportan aparte en vez de filtrarlas: subir el
        # minimo del bot se probo en backtest y no daba retorno (entre
        # -0,013% y +0,015% segun el instrumento), asi que el problema es
        # de medicion, no de trading.
        signif = [t for t in operaciones if t["notional"] >= DUST_NOTIONAL_USD]
        polvo = [t for t in operaciones if t["notional"] < DUST_NOTIONAL_USD]
        s_gan = sum(1 for t in signif if t["pnl"] > 0)
        s_tot = sum(1 for t in signif if t["pnl"] != 0)

        return {
            "symbol": symbol,
            "realized_pnl": round(realized_pnl, 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "avg_pnl_per_trade": round(realized_pnl / total_trades, 2) if total_trades > 0 else 0,
            "significant_trades": len(signif),
            "significant_win_rate": round(s_gan / s_tot * 100, 2) if s_tot else 0,
            "significant_pnl": round(sum(t["pnl"] for t in signif), 2),
            "dust_trades": len(polvo),
            "dust_pnl": round(sum(t["pnl"] for t in polvo), 2),
            "trades": list(reversed(operaciones)),  # más recientes primero
        }

    def run(self):
        """Ejecuta análisis"""
        print("📊 Analizando rendimiento...")

        # Se juntan los fills de las DOS cuentas para cada símbolo, no
        # solo la que tiene asignada hoy: QQQ y ARKK ya cambiaron de
        # cuenta una vez (2026-08-24) y sus operaciones cerradas de
        # ANTES de esa migración viven en la cuenta vieja -- si se
        # mirara solo la cuenta actual, esa historia real desaparecería
        # del dashboard sin que el símbolo haya dejado de operar.
        fills1 = self._get_fill_activities(self.account1_key, self.account1_secret, self.account1_url)
        fills2 = self._get_fill_activities(self.account2_key, self.account2_secret, self.account2_url)
        all_fills = fills1 + fills2

        for symbol in ["QQQ", "SPY", "TQQQ", "ARKK", "DIA", "IWM", "USMV", "NVDA", "AVGO", "MU", "SMH", "SOXX", "QTUM"]:
            result = self.analyze_symbol(all_fills, symbol)
            if result:
                self.results[symbol] = result
                print(f"  ✅ {symbol}: ${result['realized_pnl']} | {result['total_trades']} trades | Win rate: {result['win_rate']}%")

        return self.results

    def save_results(self, filepath="performance.json"):
        """Guarda resultados"""
        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"✅ Guardado: {filepath}")


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    analyzer.run()
    analyzer.save_results()
