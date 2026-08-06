#!/usr/bin/env python3
"""Debug: Mostrar exactamente qué fills (actividades FILL) descarga de Alpaca"""

import os
import requests


def get_fill_activities(key, secret, base_url):
    """Obtiene todas las actividades FILL"""
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }
    url = f"{base_url}/v2/account/activities"
    all_fills = []
    page_token = None

    while True:
        params = {
            "activity_types": "FILL",
            "direction": "asc",
            "page_size": 100,
        }
        if page_token:
            params["page_token"] = page_token

        response = requests.get(url, headers=headers, params=params, timeout=20)
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

    return all_fills


# Cargar credenciales
key1 = os.getenv("APCA_API_KEY_ID")
secret1 = os.getenv("APCA_API_SECRET_KEY")
url1 = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")

print("🔍 DESCARGANDO FILLS DE ALPACA (actividades FILL)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("")

fills = get_fill_activities(key1, secret1, url1)

print(f"Total de fills descargados: {len(fills)}")
print("")

if fills:
    print("Detalles de cada fill:")
    print("")

    for i, fill in enumerate(fills, 1):
        print(f"{i}. Order ID: {fill.get('order_id')}")
        print(f"   Symbol: {fill.get('symbol')}")
        print(f"   Side: {fill.get('side')} (buy/sell)")
        print(f"   Qty: {fill.get('qty')}")
        print(f"   Price: {fill.get('price')}")
        print(f"   Transaction time: {fill.get('transaction_time')}")
        print("")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    print("Resumen por símbolo:")
    print("")

    by_symbol = {}
    for fill in fills:
        symbol = fill.get("symbol", "unknown")
        by_symbol.setdefault(symbol, {"buy": 0, "sell": 0})
        side = fill.get("side")
        if side in ("buy", "sell"):
            by_symbol[symbol][side] += 1

    for symbol, counts in by_symbol.items():
        print(f"{symbol}: {counts['buy']} buys, {counts['sell']} sells")
else:
    print("❌ No se descargaron fills")
