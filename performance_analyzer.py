#!/usr/bin/env python3
"""
Analyzer de rendimiento de trading sentinelas.
Lee fills de ambas cuentas Alpaca y calcula métricas por símbolo.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests


class PerformanceAnalyzer:
    def __init__(self):
        # Cuenta 1: QQQ, QQQM, TQQQ
        self.account1 = {
            "key": os.getenv("APCA_API_KEY_ID"),
            "secret": os.getenv("APCA_API_SECRET_KEY"),
            "base_url": os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets"),
            "symbols": ["QQQ", "QQQM", "TQQQ"],
        }

        # Cuenta 2: SPY
        self.account2 = {
            "key": os.getenv("SPY_APCA_API_KEY"),
            "secret": os.getenv("SPY_APCA_API_SECRET"),
            "base_url": os.getenv("SPY_APCA_API_BASE_URL", "https://paper-api.alpaca.markets"),
            "symbols": ["SPY"],
        }

        self.results = {}

    def _get_headers(self, account):
        return {
            "APCA-API-KEY-ID": account["key"],
            "APCA-API-SECRET-KEY": account["secret"],
        }

    def _get_fills(self, account):
        """Obtiene fills de los últimos 60 días"""
        headers = self._get_headers(account)
        url = f"{account['base_url']}/v2/orders"

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"status": "closed", "limit": 500},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error obteniendo fills: {e}")
            return []

    def analyze_symbol(self, fills, symbol):
        """Analiza rendimiento para un símbolo específico"""
        symbol_fills = [f for f in fills if f.get("symbol") == symbol]

        if not symbol_fills:
            return None

        # Agrupar por order_id para obtener operaciones completas
        operations = {}
        for fill in symbol_fills:
            order_id = fill.get("order_id")
            if order_id not in operations:
                operations[order_id] = []
            operations[order_id].append(fill)

        # Calcular P&L
        realized_pnl = 0
        total_volume = 0
        winning_trades = 0
        losing_trades = 0
        trades = []

        for order_id, order_fills in operations.items():
            # Agrupar compras y ventas
            buys = [f for f in order_fills if f.get("side") == "buy"]
            sells = [f for f in order_fills if f.get("side") == "sell"]

            if buys and sells:
                buy_qty_total = sum(float(f.get("filled_qty", 0)) for f in buys)
                sell_qty_total = sum(float(f.get("filled_qty", 0)) for f in sells)

                if buy_qty_total > 0:
                    avg_buy_price = sum(float(f.get("filled_avg_price", 0)) * float(f.get("filled_qty", 0)) for f in buys) / buy_qty_total
                else:
                    avg_buy_price = 0

                if sell_qty_total > 0:
                    avg_sell_price = sum(float(f.get("filled_avg_price", 0)) * float(f.get("filled_qty", 0)) for f in sells) / sell_qty_total
                else:
                    avg_sell_price = 0

                qty = buy_qty_total

                pnl = (avg_sell_price - avg_buy_price) * qty
                realized_pnl += pnl
                total_volume += qty

                if pnl > 0:
                    winning_trades += 1
                elif pnl < 0:
                    losing_trades += 1

                trades.append({
                    "order_id": order_id,
                    "buy_price": round(avg_buy_price, 2),
                    "sell_price": round(avg_sell_price, 2),
                    "qty": round(qty, 4),
                    "pnl": round(pnl, 2),
                })

        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "symbol": symbol,
            "realized_pnl": round(realized_pnl, 2),
            "total_volume": round(total_volume, 4),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "avg_pnl_per_trade": round(realized_pnl / total_trades, 2) if total_trades > 0 else 0,
            "trades": trades,
        }

    def run(self):
        """Ejecuta análisis completo"""
        print("📊 Analizando rendimiento de sentinelas...")

        # Análisis Cuenta 1
        fills1 = self._get_fills(self.account1)
        for symbol in self.account1["symbols"]:
            result = self.analyze_symbol(fills1, symbol)
            if result:
                self.results[symbol] = result

        # Análisis Cuenta 2
        fills2 = self._get_fills(self.account2)
        for symbol in self.account2["symbols"]:
            result = self.analyze_symbol(fills2, symbol)
            if result:
                self.results[symbol] = result

        return self.results

    def save_results(self, filepath="performance.json"):
        """Guarda resultados en JSON"""
        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"✅ Resultados guardados en {filepath}")

    def get_capital_allocation(self, total_capital):
        """Calcula asignación de capital basada en rendimiento"""
        if not self.results:
            return None

        # Calcular score basado en ROI y win rate
        scores = {}
        for symbol, data in self.results.items():
            # Score = (win_rate * 0.6) + (ROI * 0.4)
            roi = (data["realized_pnl"] / total_capital * 100) if total_capital > 0 else 0
            score = (data["win_rate"] * 0.6) + (max(0, min(roi, 100)) * 0.4)
            scores[symbol] = score

        # Normalizar scores a porcentajes
        total_score = sum(scores.values())
        allocation = {}
        for symbol, score in scores.items():
            pct = (score / total_score * 100) if total_score > 0 else 25
            allocation[symbol] = round(pct, 1)

        return allocation


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    results = analyzer.run()
    analyzer.save_results()

    print("\n📈 Rendimiento por símbolo:")
    for symbol, data in results.items():
        print(f"\n{symbol}:")
        print(f"  P&L Realizado: ${data['realized_pnl']}")
        print(f"  Win Rate: {data['win_rate']}%")
        print(f"  Total Operaciones: {data['total_trades']}")
        print(f"  P&L Promedio: ${data['avg_pnl_per_trade']}")
