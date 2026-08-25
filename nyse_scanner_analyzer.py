#!/usr/bin/env python3
"""
Analiza el estado del NYSE Scanner para el dashboard. Caso distinto al
resto de la familia: opera un símbolo VARIABLE (uno a la vez, nunca
fijo), así que no encaja en el patrón BOTS={symbol: repo} del resto —
acá se lee su propio state/execution_state.json (status: flat /
pending_entry / in_position) y, si hay posición abierta, se consulta
Alpaca por ESE símbolo puntual (no uno fijo).
"""

import base64
import csv
import io
import json
import os
from pathlib import Path

import requests

GITHUB_OWNER = "anonimusnonimus30-beep"
GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("BOTS_READ_TOKEN", "")
REPO = "nyse_scanner_sentinel"

# Misma cuenta de derivados (account1/FOT6) que QQQM/TQQQ/ARKK/DIA/IWM/USMV/NVDA/AVGO/MU.
ACCOUNT_KEY = os.getenv("APCA_API_KEY_ID")
ACCOUNT_SECRET = os.getenv("APCA_API_SECRET_KEY")
ACCOUNT_URL = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")


def safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _fetch_json(filename):
    if not GITHUB_TOKEN:
        print(f"⚠️ BOTS_READ_TOKEN no configurado, omitiendo {REPO}/{filename}")
        return None
    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{REPO}/contents/{filename}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Error leyendo {REPO}/{filename}: HTTP {response.status_code}")
            return None
        data = response.json()
        if isinstance(data, dict) and "content" in data:
            return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return None
    except Exception as e:
        print(f"⚠️ Error leyendo {REPO}/{filename}: {e}")
        return None


def _fetch_trade_log():
    if not GITHUB_TOKEN:
        return []
    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{REPO}/contents/state/trade_log.csv"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.raw+json"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return []
        return list(csv.DictReader(io.StringIO(response.text)))
    except Exception as e:
        print(f"⚠️ Error leyendo {REPO}/state/trade_log.csv: {e}")
        return []


def _get_position(symbol):
    if not ACCOUNT_KEY or not ACCOUNT_SECRET:
        return None
    headers = {"APCA-API-KEY-ID": ACCOUNT_KEY, "APCA-API-SECRET-KEY": ACCOUNT_SECRET}
    try:
        r = requests.get(f"{ACCOUNT_URL}/v2/positions/{symbol}", headers=headers, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error obteniendo posición {symbol} (NYSE Scanner): {e}")
        return None


def analyze():
    execution_state = _fetch_json("state/execution_state.json") or {"status": "flat"}
    today_signals = _fetch_json("state/today_signals.json") or {}

    status = execution_state.get("status", "flat")
    result = {
        "status": status,
        "symbol": execution_state.get("symbol"),
        "signal_date": execution_state.get("signal_date") or execution_state.get("queued_at", "")[:10],
        "score": execution_state.get("score"),
        "entry_date": execution_state.get("entry_date"),
        "entry_price": execution_state.get("entry_price"),
        "days_held": execution_state.get("days_held", 0),
        "position": None,
        "today_evaluated": today_signals.get("evaluated"),
        "today_signals_count": len(today_signals.get("signals", [])),
        "today_date": today_signals.get("date"),
    }

    if status == "in_position" and result["symbol"] and not execution_state.get("dry_run"):
        position = _get_position(result["symbol"])
        if position:
            result["position"] = {
                "qty": safe_float(position.get("qty")),
                "market_value": safe_float(position.get("market_value")),
                "current_price": safe_float(position.get("current_price")),
                "unrealized_pl": safe_float(position.get("unrealized_pl")),
                "unrealized_plpc": safe_float(position.get("unrealized_plpc")) * 100,
            }

    label = {
        "flat": "Sin posición, esperando señal",
        "pending_entry": f"Señal en cola: {result['symbol']} (score {result['score']}) — entra al cierre de la próxima sesión",
        "in_position": f"En posición: {result['symbol']} desde {result['entry_date']} (día {result['days_held']}/15)",
    }.get(status, status)
    result["status_label"] = label

    trades = _fetch_trade_log()
    for t in trades:
        t["pnl_usd"] = safe_float(t.get("pnl_usd"))
        t["pnl_pct"] = safe_float(t.get("pnl_pct"))
    trades.sort(key=lambda t: t.get("exit_date", ""), reverse=True)

    total_trades = len(trades)
    winning = sum(1 for t in trades if t["pnl_usd"] > 0)
    realized_pnl = round(sum(t["pnl_usd"] for t in trades), 2)

    result["trades"] = trades[:20]  # más recientes primero
    result["total_trades"] = total_trades
    result["win_rate"] = round(winning / total_trades * 100, 1) if total_trades else 0
    result["realized_pnl"] = realized_pnl

    print(f"✅ NYSE Scanner: {label} | {total_trades} operaciones cerradas, ${realized_pnl} realizado")
    return result


def save_results(result, filepath="nyse_scanner.json"):
    with open(filepath, "w") as f:
        json.dump(result, f, indent=2)
    print(f"✅ Guardado: {filepath}")


if __name__ == "__main__":
    save_results(analyze())
