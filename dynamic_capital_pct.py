#!/usr/bin/env python3
"""
Calcula el MAX_POSITION_PCT real (banda 1%-3% de su cuenta) de cada
sentinel satélite de la cuenta de derivados, según su rendimiento
(mismo score de capital_allocator.py: 60% win_rate + 40% ROI). Corre
semanalmente (ver .github/workflows/update-dynamic-capital.yml) y
publica dynamic_position_pct.json en este repo público — cada bot lo
lee en su propia corrida (igual patrón que el Risk Engine) en vez de
depender solo del secret fijo MAX_POSITION_PCT.

TQQQ es el único miembro de su nivel (satellite_proven), así que no
hay contra quién redistribuir: siempre se queda con el 3% entero de
ese nivel. Los demás niveles sí reparten el presupuesto del nivel
entre sus miembros según score, con el mismo piso (mitad del reparto
parejo) que ya usa capital_allocator.py para no dejar a nadie en casi
cero por una mala racha corta.
"""

import json
from datetime import datetime, timezone

from capital_allocator import CapitalAllocator, MIN_SHARE_OF_EVEN_SPLIT

OUTPUT_FILE = "dynamic_position_pct.json"

# Presupuesto REAL (% de la cuenta de derivados) de cada nivel satélite,
# igual a la suma de los MAX_POSITION_PCT que se fijaron el 2026-08-27.
DERIVATIVES_TIERS = {
    "satellite_proven": {"TQQQ": 3.0},
    "satellite_new": {"ARKK": 1.5, "DIA": 1.5, "IWM": 1.5, "USMV": 1.5},
    "satellite_stocks": {"NVDA": 1.25, "AVGO": 1.25, "MU": 1.25},
    "satellite_thematic": {"SMH": 1.25, "SOXX": 1.25, "QTUM": 1.25},
}


def compute(allocator: CapitalAllocator) -> dict:
    total_capital = allocator.get_total_capital()
    result = {}

    for tier, baseline in DERIVATIVES_TIERS.items():
        symbols = list(baseline.keys())
        budget = sum(baseline.values())

        if len(symbols) == 1:
            result[symbols[0]] = round(budget, 3)
            continue

        scores = {s: allocator._score(s, total_capital) for s in symbols}
        total_score = sum(scores.values())

        shares = {}
        for s in symbols:
            share = scores[s] / total_score if total_score > 0 else 1.0 / len(symbols)
            even_split = 1.0 / len(symbols)
            floor = even_split * MIN_SHARE_OF_EVEN_SPLIT
            cap = 1.0 - floor * (len(symbols) - 1)
            shares[s] = max(floor, min(cap, share))

        tier_total_share = sum(shares.values())
        for s in symbols:
            result[s] = round(shares[s] / tier_total_share * budget, 3)

    return result


def main():
    allocator = CapitalAllocator()
    positions = compute(allocator)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "positions": positions,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"✅ {OUTPUT_FILE} actualizado:")
    print(json.dumps(positions, indent=2))


if __name__ == "__main__":
    main()
