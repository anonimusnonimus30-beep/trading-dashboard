#!/usr/bin/env python3
"""
Asignador de capital dinámico basado en rendimiento.
Calcula qué porcentaje del capital total debe destinarse a cada sentinela.
"""

import json
import os
from pathlib import Path
import requests


class CapitalAllocator:
    def __init__(self, performance_file="performance.json"):
        self.performance_file = performance_file
        self.performance_data = self._load_performance()
        self.account1_key = os.getenv("APCA_API_KEY_ID")
        self.account1_secret = os.getenv("APCA_API_SECRET_KEY")
        self.account1_url = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")
        self.account2_key = os.getenv("SPY_APCA_API_KEY")
        self.account2_secret = os.getenv("SPY_APCA_API_SECRET")
        self.account2_url = os.getenv("SPY_APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

    def _load_performance(self):
        """Carga datos de rendimiento"""
        if not Path(self.performance_file).exists():
            return {}
        with open(self.performance_file) as f:
            return json.load(f)

    def _get_account_value(self, key, secret, base_url):
        """Obtiene el cash + equity de una cuenta"""
        try:
            headers = {
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
            }
            response = requests.get(
                f"{base_url}/v2/account",
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            account = response.json()
            equity = float(account.get("equity", 0))
            cash = float(account.get("cash", 0))
            return equity, cash
        except Exception as e:
            print(f"Error obteniendo valor de cuenta: {e}")
            return 0, 0

    def get_total_capital(self):
        """Obtiene capital total de ambas cuentas"""
        equity1, _ = self._get_account_value(self.account1_key, self.account1_secret, self.account1_url)
        equity2, _ = self._get_account_value(self.account2_key, self.account2_secret, self.account2_url)
        return equity1 + equity2

    def calculate_allocation(self):
        """
        Calcula asignación de capital basada en:
        1. Win rate (60%)
        2. ROI realizado (40%)
        """
        if not self.performance_data:
            # Default allocation si no hay datos
            return {
                "QQQ": 25,
                "QQQM": 25,
                "TQQQ": 25,
                "SPY": 25,
            }

        total_capital = self.get_total_capital()
        scores = {}

        for symbol, data in self.performance_data.items():
            win_rate = data.get("win_rate", 50)
            pnl = data.get("realized_pnl", 0)
            roi = (pnl / total_capital * 100) if total_capital > 0 else 0

            # Score ponderado: 60% win_rate + 40% ROI
            score = (win_rate * 0.6) + (max(-50, min(roi, 50)) * 0.4)
            scores[symbol] = max(0, score)

        # Normalizar a porcentajes
        total_score = sum(scores.values())
        allocation = {}

        for symbol in ["QQQ", "QQQM", "TQQQ", "SPY"]:
            if total_score > 0:
                pct = (scores.get(symbol, 0) / total_score * 100)
            else:
                pct = 25
            allocation[symbol] = round(max(10, min(40, pct)), 1)  # Min 10%, Max 40%

        # Ajustar para que sume 100%
        total = sum(allocation.values())
        if total != 100:
            adjustment = (100 - total) / 4
            for symbol in allocation:
                allocation[symbol] = round(allocation[symbol] + adjustment, 1)

        return allocation

    def save_allocation(self, filepath="capital_allocation.json"):
        """Guarda asignación de capital"""
        allocation = self.calculate_allocation()
        total_capital = self.get_total_capital()

        data = {
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "total_capital": round(total_capital, 2),
            "allocation_pct": allocation,
            "allocation_usd": {
                symbol: round(total_capital * pct / 100, 2)
                for symbol, pct in allocation.items()
            },
            "trade_size_range": {
                symbol: {
                    "min": round(total_capital * pct / 100 * 0.01, 2),  # 1%
                    "max": round(total_capital * pct / 100 * 0.03, 2),  # 3%
                }
                for symbol, pct in allocation.items()
            },
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Asignación de capital guardada en {filepath}")
        return data


if __name__ == "__main__":
    allocator = CapitalAllocator()
    result = allocator.save_allocation()

    print("\n💰 Asignación de Capital:")
    print(f"Capital Total: ${result['total_capital']}")
    print("\nPorcentaje:")
    for symbol, pct in result["allocation_pct"].items():
        print(f"  {symbol}: {pct}%")
    print("\nRango de Operaciones (1-3%):")
    for symbol, range_data in result["trade_size_range"].items():
        print(f"  {symbol}: ${range_data['min']} - ${range_data['max']}")
