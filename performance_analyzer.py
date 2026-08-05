#!/usr/bin/env python3
"""
Analyzer de rendimiento simplificado que evita errores de tipo.
"""

import os
import json
from pathlib import Path
import requests


def safe_float(value):
    """Convierte valor a float de forma segura"""
    try:
        if isinstance(value, str):
            return float(value.strip())
        return float(value)
    except (ValueError, TypeError):
        return 0.0


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

    def _get_fills(self, key, secret, base_url):
        """Obtiene fills cerrados"""
        headers = self._get_headers(key, secret)
        url = f"{base_url}/v2/orders"

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"status": "closed", "limit": 500},
                timeout=20,
            )
            response.raise_for_status()
            return response.json() if response.ok else []
        except Exception as e:
            print(f"⚠️ Error obteniendo fills: {e}")
            return []

    def analyze_symbol(self, fills, symbol):
        """Analiza un símbolo específico"""
        symbol_fills = [f for f in fills if f.get("symbol") == symbol]

        if not symbol_fills:
            return None

        realized_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        trades = []

        # Agrupar por order_id
        operations = {}
        for fill in symbol_fills:
            order_id = fill.get("order_id", "unknown")
            if order_id not in operations:
                operations[order_id] = []
            operations[order_id].append(fill)

        # Analizar cada operación
        for order_id, order_fills in operations.items():
            buys = [f for f in order_fills if f.get("side") == "buy"]
            sells = [f for f in order_fills if f.get("side") == "sell"]

            if buys and sells:
                # Calcular precios promedio
                buy_qty = sum(safe_float(f.get("filled_qty", 0)) for f in buys)
                sell_qty = sum(safe_float(f.get("filled_qty", 0)) for f in sells)

                if buy_qty > 0:
                    avg_buy = sum(safe_float(f.get("filled_avg_price", 0)) * safe_float(f.get("filled_qty", 0)) for f in buys) / buy_qty
                else:
                    avg_buy = 0.0

                if sell_qty > 0:
                    avg_sell = sum(safe_float(f.get("filled_avg_price", 0)) * safe_float(f.get("filled_qty", 0)) for f in sells) / sell_qty
                else:
                    avg_sell = 0.0

                pnl = (avg_sell - avg_buy) * buy_qty
                realized_pnl += pnl

                if pnl > 0:
                    winning_trades += 1
                elif pnl < 0:
                    losing_trades += 1

                trades.append({
                    "order_id": order_id[:8],
                    "buy_price": round(avg_buy, 2),
                    "sell_price": round(avg_sell, 2),
                    "qty": round(buy_qty, 4),
                    "pnl": round(pnl, 2),
                })

        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "symbol": symbol,
            "realized_pnl": round(realized_pnl, 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "avg_pnl_per_trade": round(realized_pnl / total_trades, 2) if total_trades > 0 else 0,
            "trades": trades,
        }

    def run(self):
        """Ejecuta análisis"""
        print("📊 Analizando rendimiento...")

        fills1 = self._get_fills(self.account1_key, self.account1_secret, self.account1_url)
        for symbol in ["QQQ", "QQQM", "TQQQ"]:
            result = self.analyze_symbol(fills1, symbol)
            if result:
                self.results[symbol] = result
                print(f"  ✅ {symbol}: ${result['realized_pnl']} | Win rate: {result['win_rate']}%")

        fills2 = self._get_fills(self.account2_key, self.account2_secret, self.account2_url)
        for symbol in ["SPY"]:
            result = self.analyze_symbol(fills2, symbol)
            if result:
                self.results[symbol] = result
                print(f"  ✅ {symbol}: ${result['realized_pnl']} | Win rate: {result['win_rate']}%")

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
