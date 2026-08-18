#!/usr/bin/env python3
"""
Asignador de capital dinámico basado en rendimiento.
Calcula qué porcentaje del capital total debe destinarse a cada sentinela.

ESTRUCTURA POR NIVELES (2026-08-18)
------------------------------------
Antes, los 5 símbolos competían libres entre 10% y 40% solo por
win_rate/ROI. Eso trataba a QQQM como si diversificara frente a QQQ
cuando en realidad sigue el mismo índice (Nasdaq-100) con otro modelo
de scoring — no reduce riesgo, solo duplica exposición. Y dejaba a
TQQQ (3x apalancado) y ARKK (cartera activa concentrada) competir por
el mismo presupuesto que QQQ/SPY pese a tener drawdowns 2-3x mayores.

Ahora el presupuesto se reparte primero por NIVEL, con un peso fijo, y
recién dentro de cada nivel el score de rendimiento (win_rate/ROI)
decide cómo se reparte ESE presupuesto entre sus miembros. Los cambios
de asignación por rendimiento nunca sacan a un símbolo de su nivel ni
le quitan presupuesto a otro nivel.

  - core (80%): QQQ, SPY — índices amplios, sin apalancamiento.
  - satellite (20%): TQQQ, ARKK — apalancado / cartera concentrada,
    mayor riesgo, se limita a una porción chica a propósito.
  - paused (0%): QQQM — mismo índice que QQQ sin aportar
    diversificación real. Sigue corriendo (señal, estado, log,
    reporte semanal de auto-aprendizaje) para no perder historial,
    solo no recibe capital hasta que haya una razón concreta para
    reactivarlo.
"""

import json
import os
from pathlib import Path
import requests

TIER_OF = {
    "QQQ": "core",
    "SPY": "core",
    "TQQQ": "satellite",
    "ARKK": "satellite",
    "QQQM": "paused",
}

TIER_BUDGET_PCT = {
    "core": 80.0,
    "satellite": 20.0,
    "paused": 0.0,
}

# Dentro de un nivel de 2 miembros, el de peor score no puede quedar
# por debajo de este piso del presupuesto del nivel (evita que un mal
# tramo corto deje a un símbolo del núcleo en casi cero).
MIN_SHARE_WITHIN_TIER = 0.30


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

    def _score(self, symbol, total_capital):
        """Score de rendimiento (60% win_rate + 40% ROI) de un símbolo.
        Sin datos todavía, score neutro (no penaliza ni favorece)."""
        data = self.performance_data.get(symbol)
        if not data:
            return 50.0

        win_rate = data.get("win_rate", 50)
        pnl = data.get("realized_pnl", 0)
        roi = (pnl / total_capital * 100) if total_capital > 0 else 0
        score = (win_rate * 0.6) + (max(-50, min(roi, 50)) * 0.4)
        return max(0.0, score)

    def calculate_allocation(self):
        """
        Reparte el capital en dos pasos:
        1. Por NIVEL, con presupuesto fijo (TIER_BUDGET_PCT) — esta es
           la lógica base y no la mueve el rendimiento.
        2. Dentro de cada nivel, por score de rendimiento (60% win
           rate + 40% ROI), entre sus miembros — acá es donde
           win_rate/ROI sí deciden, pero solo redistribuyen el
           presupuesto YA asignado a ese nivel.
        """
        total_capital = self.get_total_capital()

        tiers = {}
        for symbol, tier in TIER_OF.items():
            tiers.setdefault(tier, []).append(symbol)

        allocation = {}

        for tier, symbols in tiers.items():
            budget = TIER_BUDGET_PCT[tier]

            if budget <= 0:
                for symbol in symbols:
                    allocation[symbol] = 0.0
                continue

            scores = {s: self._score(s, total_capital) for s in symbols}
            total_score = sum(scores.values())

            for symbol in symbols:
                if total_score > 0:
                    share = scores[symbol] / total_score
                else:
                    share = 1.0 / len(symbols)

                if len(symbols) > 1:
                    share = max(MIN_SHARE_WITHIN_TIER, min(1 - MIN_SHARE_WITHIN_TIER, share))

                allocation[symbol] = share

            # Renormalizar el nivel a 1.0 por si el piso/techo movió la suma
            tier_total = sum(allocation[s] for s in symbols)
            for symbol in symbols:
                allocation[symbol] = round(allocation[symbol] / tier_total * budget, 1)

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
