#!/usr/bin/env python3
"""Debug: Mostrar exactamente qué fills está descargando de Alpaca"""

import os
import json
import requests

def get_fills(key, secret, base_url):
    """Obtiene todos los fills cerrados"""
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }
    url = f"{base_url}/v2/orders"
    all_fills = []
    after = None

    while True:
        params = {"status": "closed", "limit": 500}
        if after:
            params["after"] = after

        response = requests.get(url, headers=headers, params=params, timeout=20)
        fills = response.json() if response.ok else []

        if not fills:
            break

        all_fills.extend(fills)

        if len(fills) < 500:
            break

        after = fills[-1].get("created_at")

    return all_fills


# Cargar credenciales
key1 = os.getenv("APCA_API_KEY_ID")
secret1 = os.getenv("APCA_API_SECRET_KEY")
url1 = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")

print("🔍 DESCARGANDO FILLS DE ALPACA")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("")

fills = get_fills(key1, secret1, url1)

print(f"Total de fills descargados: {len(fills)}")
print("")

if fills:
    print("Detalles de cada fill:")
    print("")

    for i, fill in enumerate(fills, 1):
        print(f"{i}. Order ID: {fill.get('order_id')}")
        print(f"   Symbol: {fill.get('symbol')}")
        print(f"   Side: {fill.get('side')} (buy/sell)")
        print(f"   Qty: {fill.get('filled_qty')}")
        print(f"   Price: {fill.get('filled_avg_price')}")
        print(f"   Created: {fill.get('created_at')}")
        print("")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    print("Análisis por orden:")
    print("")

    # Agrupar por order_id
    by_order = {}
    for fill in fills:
        order_id = fill.get("order_id", "unknown")
        if order_id not in by_order:
            by_order[order_id] = []
        by_order[order_id].append(fill)

    for order_id, order_fills in by_order.items():
        buys = [f for f in order_fills if f.get("side") == "buy"]
        sells = [f for f in order_fills if f.get("side") == "sell"]

        print(f"Order: {order_id}")
        print(f"  Buys: {len(buys)}")
        print(f"  Sells: {len(sells)}")

        if buys and sells:
            print(f"  ✅ COMPLETA (buy + sell)")
        elif buys:
            print(f"  ⚠️ INCOMPLETA (solo buy)")
        elif sells:
            print(f"  ⚠️ INCOMPLETA (solo sell)")
        print("")
else:
    print("❌ No se descargaron fills")
