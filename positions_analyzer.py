#!/usr/bin/env python3
"""
Combina la posición abierta real (Alpaca) con la última señal
calculada por cada sentinel (leída del propio repo del bot) para
mostrar qué está pasando ahora y qué está pendiente de ejecutar,
no solo el historial de operaciones cerradas.
"""

import base64
import json
import os
import requests

GITHUB_OWNER = "anonimusnonimus30-beep"
GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("BOTS_READ_TOKEN", "")

# BOTS_READ_TOKEN no tiene permiso de "Actions" (solo "Contents"), así
# que el estado real del workflow de cada bot no se puede consultar
# vía API con este token. Mientras tanto, la lista de suspendidos se
# mantiene a mano acá — actualízala cuando reactives/pauses un bot.
# Reestructurado 2026-08-24: QQQ y SPY quedaron solos en la cuenta
# account2 (antes la de SPY); QQQM, TQQQ, ARKK, DIA, IWM y USMV pasaron
# todos a account1 (antes la de QQQ/QQQM/TQQQ). Ninguno queda
# suspendido: los seis se reactivaron con la migración.
SUSPENDED_SYMBOLS = set()

BOTS = {
    "QQQ": {
        "repo": "qqq-sentinel",
        "state_file": "qqq_sentinel_state.json",
        "execution_file": "qqq_execution_state.json",
        "account": "account2",
    },
    "SPY": {
        "repo": "spy_sentinel",
        "state_file": "spy_sentinel_state.json",
        "execution_file": "spy_execution_state.json",
        "account": "account2",
    },
    "QQQM": {
        "repo": "qqqm_sentinel",
        "state_file": "qqqm_sentinel_state.json",
        "execution_file": "qqqm_execution_state.json",
        "account": "account1",
    },
    "TQQQ": {
        "repo": "tqqq_sentinel",
        "state_file": "tqqq_sentinel_state.json",
        "execution_file": "tqqq_execution_state.json",
        "account": "account1",
    },
    "ARKK": {
        "repo": "splg_sentinel",
        "state_file": "arkk_sentinel_state.json",
        "execution_file": "arkk_execution_state.json",
        "account": "account1",
    },
    "DIA": {
        "repo": "dia_sentinel",
        "state_file": "dia_sentinel_state.json",
        "execution_file": "dia_execution_state.json",
        "account": "account1",
    },
    "IWM": {
        "repo": "iwm_sentinel",
        "state_file": "iwm_sentinel_state.json",
        "execution_file": "iwm_execution_state.json",
        "account": "account1",
    },
    "USMV": {
        "repo": "usmv_sentinel",
        "state_file": "usmv_sentinel_state.json",
        "execution_file": "usmv_execution_state.json",
        "account": "account1",
    },
    "NVDA": {
        "repo": "nvda_sentinel",
        "state_file": "nvda_sentinel_state.json",
        "execution_file": "nvda_execution_state.json",
        "account": "account1",
    },
    "AVGO": {
        "repo": "avgo_sentinel",
        "state_file": "avgo_sentinel_state.json",
        "execution_file": "avgo_execution_state.json",
        "account": "account1",
    },
    "MU": {
        "repo": "mu_sentinel",
        "state_file": "mu_sentinel_state.json",
        "execution_file": "mu_execution_state.json",
        "account": "account1",
    },
    "SMH": {
        "repo": "smh_sentinel",
        "state_file": "smh_sentinel_state.json",
        "execution_file": "smh_execution_state.json",
        "account": "account1",
    },
    "SOXX": {
        "repo": "soxx_sentinel",
        "state_file": "soxx_sentinel_state.json",
        "execution_file": "soxx_execution_state.json",
        "account": "account1",
    },
    "QTUM": {
        "repo": "qtum_sentinel",
        "state_file": "qtum_sentinel_state.json",
        "execution_file": "qtum_execution_state.json",
        "account": "account1",
    },
}


def safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def fetch_raw_json(repo, filename):
    """Lee un archivo de estado del repo del bot vía la API de GitHub (los 4 repos son privados)."""
    if not GITHUB_TOKEN:
        print(f"⚠️ BOTS_READ_TOKEN no configurado, omitiendo {repo}/{filename}")
        return None

    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(
                f"⚠️ Error leyendo {repo}/{filename}: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )
            return None

        data = response.json()
        if isinstance(data, dict) and "content" in data:
            decoded = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(decoded)

        return None
    except Exception as e:
        print(f"⚠️ Error leyendo {repo}/{filename}: {e}")
        return None


class PositionsAnalyzer:
    def __init__(self):
        self.account1_key = os.getenv("APCA_API_KEY_ID")
        self.account1_secret = os.getenv("APCA_API_SECRET_KEY")
        self.account1_url = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")

        self.account2_key = os.getenv("SPY_APCA_API_KEY")
        self.account2_secret = os.getenv("SPY_APCA_API_SECRET")
        self.account2_url = os.getenv("SPY_APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

    def _headers(self, key, secret):
        return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    def _get_position(self, key, secret, base_url, symbol):
        try:
            response = requests.get(
                f"{base_url}/v2/positions/{symbol}",
                headers=self._headers(key, secret),
                timeout=20,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ Error obteniendo posición {symbol}: {e}")
            return None

    def analyze(self):
        results = {}

        for symbol, cfg in BOTS.items():
            if cfg["account"] == "account1":
                key, secret, url = self.account1_key, self.account1_secret, self.account1_url
            else:
                key, secret, url = self.account2_key, self.account2_secret, self.account2_url

            position = self._get_position(key, secret, url, symbol)

            if position:
                position_info = {
                    "has_position": True,
                    "qty": safe_float(position.get("qty")),
                    "avg_entry_price": safe_float(position.get("avg_entry_price")),
                    "current_price": safe_float(position.get("current_price")),
                    "market_value": safe_float(position.get("market_value")),
                    "cost_basis": safe_float(position.get("cost_basis")),
                    "unrealized_pl": safe_float(position.get("unrealized_pl")),
                    "unrealized_plpc": safe_float(position.get("unrealized_plpc")) * 100,
                }
            else:
                position_info = {
                    "has_position": False,
                    "qty": 0.0,
                    "avg_entry_price": 0.0,
                    "current_price": 0.0,
                    "market_value": 0.0,
                    "cost_basis": 0.0,
                    "unrealized_pl": 0.0,
                    "unrealized_plpc": 0.0,
                }

            sentinel_state = fetch_raw_json(cfg["repo"], cfg["state_file"]) or {}
            execution_state = fetch_raw_json(cfg["repo"], cfg["execution_file"]) or {}

            signal_target = sentinel_state.get("last_target_exposure")
            executed_target = execution_state.get("last_executed_target")

            pending_rebalance = (
                signal_target is not None
                and executed_target is not None
                and safe_float(signal_target) != safe_float(executed_target)
            )

            suspended = symbol in SUSPENDED_SYMBOLS

            results[symbol] = {
                "position": position_info,
                "signal": {
                    "signal_date": sentinel_state.get("last_date"),
                    "target_exposure_pct": signal_target,
                    "last_executed_target_pct": executed_target,
                    "last_action": execution_state.get("action"),
                    "last_checked_at": execution_state.get("last_checked_at"),
                    "pending_rebalance": pending_rebalance,
                },
                "suspended": suspended,
            }

            status = "posición abierta" if position_info["has_position"] else "sin posición"
            suspended_label = " | ⏸️ SUSPENDIDO" if suspended else ""
            print(
                f"  ✅ {symbol}: {status} | target señal: {signal_target}% "
                f"| último ejecutado: {executed_target}%{suspended_label}"
            )

        return results

    def save_results(self, results, filepath="positions.json"):
        with open(filepath, "w") as f:
            json.dump(results, f, indent=2)
        print(f"✅ Guardado: {filepath}")


if __name__ == "__main__":
    analyzer = PositionsAnalyzer()
    data = analyzer.analyze()
    analyzer.save_results(data)
