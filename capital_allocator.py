#!/usr/bin/env python3
"""
Asignador de capital dinámico basado en rendimiento.
Calcula qué porcentaje del capital total debe destinarse a cada sentinela.

ESTRUCTURA POR NIVELES (actualizado 2026-08-24)
------------------------------------------------
El presupuesto se reparte primero por NIVEL, con un peso fijo, y recién
dentro de cada nivel el score de rendimiento (win_rate/ROI) decide cómo
se reparte ESE presupuesto entre sus miembros. Los cambios de
asignación por rendimiento nunca sacan a un símbolo de su nivel ni le
quitan presupuesto a otro nivel.

Desde 2026-08-24, QQQ y SPY quedaron solos en su propia cuenta de
Alpaca (antes QQQ compartía cuenta con QQQM/TQQQ). Todo lo demás — los
ETFs de índice (TQQQ/ARKK/DIA/IWM/USMV), tres acciones individuales
(NVDA/AVGO/MU) y, desde 2026-08-26, tres ETFs temáticos que le ganan a
QQQ en CAGR y retorno total (SMH/SOXX/QTUM) — se movió a la otra
cuenta, que ahora no tiene ni QQQ ni SPY.

QQQM se retiró el 2026-08-26: su señal táctica nunca validó ventaja
real (backtest con generalización mixta, peor Sharpe que buy&hold; en
vivo, 50% de win rate y PnL negativo) sobre un símbolo que además
trackea el mismo índice que QQQ con un motor peor. Se liquidó su
posición y se apagó el bot; su cupo de capital se lo absorbió QQQ
(MAX_POSITION_PCT 45%->55% en su propia cuenta).

BILLETERA DINÁMICA (2026-08-27)
--------------------------------
Hasta acá, cada repo tenía además un tope fijo en dólares
(MAX_NOTIONAL_USD, ~$3000 la mayoría) que en la práctica era el
verdadero límite de la posición — muy por debajo del % pensado sobre
una cuenta que ya creció a ~$100k por cuenta. Subir MAX_POSITION_PCT
(como se hizo con QQQ) no tenía ningún efecto real mientras ese techo
siguiera ahí. Se sacó el tope fijo de los 13 repos: ahora el tamaño de
cada posición es puramente % del equity REAL de su cuenta en ese
momento (escala sola si la cuenta crece o se achica), y los satélites
de la cuenta de derivados se re-calibraron para invertir entre 1% y
3% de esa cuenta cada uno (antes 5-12%, con el mismo orden relativo:
TQQQ el más grande por ser el de historial más probado, acciones
individuales y temáticos los más chicos por concentrar más riesgo
idiosincrático). Los porcentajes de acá siguen expresados como % del
capital COMBINADO de ambas cuentas (la mitad del % real de cada
repo), solo para que el reparto por nivel sea comparable entre sí.

  - core (50%): QQQ, SPY — únicos en su cuenta, índices amplios sin
    apalancamiento. Repo: 55%/45% de su cuenta.
  - satellite_proven (1.5%): TQQQ — historial real ya acumulado en
    paper trading. Repo: 3% de su cuenta.
  - satellite_new (3%): ARKK, DIA, IWM, USMV — ETFs, presupuesto chico
    a propósito hasta que acumulen historial propio. Repo: 1.5% cada
    uno.
  - satellite_stocks (1.875%): NVDA, AVGO, MU — acciones individuales,
    presupuesto más chico que los ETFs a propósito: sin la
    diversificación de un ETF, el riesgo idiosincrático de una sola
    acción (gaps de resultados trimestrales, noticias específicas de
    la empresa) es estructuralmente mayor. Repo: 1.25% cada una.
  - satellite_thematic (1.875%): SMH, SOXX, QTUM — ETFs sectoriales/
    temáticos concentrados (semiconductores x2, IA/cuántica) que le
    ganan a QQQ en CAGR y retorno total en todas las ventanas
    probadas, pero con más drawdown por estar concentrados en un
    sector en vez de diversificados como QQQ. Repo: 1.25% cada uno.

Con 5 niveles sumando ~58.25% queda un colchón grande (~41.75%) a
propósito: son 11 bots satélite corriendo en paralelo en la misma
cuenta, así que cada uno se queda chico (1-3%) para que la cuenta
nunca dependa de que todos acierten a la vez.
"""

import json
import os
from pathlib import Path
import requests

TIER_OF = {
    "QQQ": "core",
    "SPY": "core",
    "TQQQ": "satellite_proven",
    "ARKK": "satellite_new",
    "DIA": "satellite_new",
    "IWM": "satellite_new",
    "USMV": "satellite_new",
    "NVDA": "satellite_stocks",
    "AVGO": "satellite_stocks",
    "MU": "satellite_stocks",
    "SMH": "satellite_thematic",
    "SOXX": "satellite_thematic",
    "QTUM": "satellite_thematic",
}

TIER_BUDGET_PCT = {
    "core": 50.0,
    "satellite_proven": 1.5,
    "satellite_new": 3.0,
    "satellite_stocks": 1.875,
    "satellite_thematic": 1.875,
}

# Dentro de un nivel, el de peor score no puede quedar por debajo de
# esta fracción del reparto parejo (evita que un mal tramo corto deje
# a un símbolo en casi cero). Se expresa como fracción del reparto
# parejo (1/N miembros) en vez de un piso fijo, para que siga siendo
# coherente en niveles de 2 miembros (core, satellite_proven) y de 4
# (satellite_new) por igual.
MIN_SHARE_OF_EVEN_SPLIT = 0.5


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
        Sin datos todavía, score neutro (no penaliza ni favorece). Un
        símbolo con 0 operaciones (recién migrado de cuenta, o recién
        integrado) cuenta como "sin datos" — si no, win_rate=0% de una
        muestra vacía se leería como el peor desempeño posible."""
        data = self.performance_data.get(symbol)
        if not data or data.get("total_trades", 0) == 0:
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
                    even_split = 1.0 / len(symbols)
                    floor = even_split * MIN_SHARE_OF_EVEN_SPLIT
                    cap = 1.0 - floor * (len(symbols) - 1)
                    share = max(floor, min(cap, share))

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
