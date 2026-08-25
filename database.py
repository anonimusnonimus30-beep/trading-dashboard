#!/usr/bin/env python3
"""
Base de datos SQLite con el histórico y estado actual de los 5 bots,
para análisis propio fuera del dashboard (no la usa el HTML generado).

Se corre en cada actualización del workflow, después de
performance_analyzer.py / positions_analyzer.py / capital_allocator.py:

- trades / signal_history: se reconstruyen completos en cada corrida
  desde performance.json y desde el CSV de señales de cada bot (que ya
  trae el historial completo desde que arrancó cada uno). Usan
  INSERT OR IGNORE sobre una clave única, así que reimportar el
  histórico completo cada vez no duplica filas.

- positions_snapshot / performance_snapshot / capital_allocation_snapshot:
  agregan UNA fila nueva por símbolo en cada corrida (con snapshot_at).
  Su "histórico" arranca desde que esta base existe — antes de esto el
  dashboard solo guardaba el último estado y lo sobreescribía cada vez,
  así que no hay forma de recuperar snapshots anteriores a hoy.

NOTA sobre SPY: antes del 2026-08-18 su señal se calculaba con el
precio de QQQM, no el de SPY (bug de copy-paste ya corregido). Las
filas de signal_history de SPY con signal_date anterior a esa fecha
reflejan ese bug — no es un error de esta base, es historial real de
lo que el bot vio en ese momento.
"""

import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

GITHUB_OWNER = "anonimusnonimus30-beep"
GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("BOTS_READ_TOKEN", "")

DB_FILE = "sentinels.db"

# format "v5": qqq_sentinel_90_10.py (date,close,v5_active,bear_confirmed,target_exposure,changed)
# format "score": el resto (date,symbol,price,score,target_exposure_pct,trend,momentum,
#                  volatility,volume,quality,rsi,adx,atr_pct,roc20,roc60,drawdown,regime)
SIGNAL_LOGS = {
    "QQQ": {"repo": "qqq-sentinel", "file": "qqq_sentinel_log.csv", "format": "v5"},
    "SPY": {"repo": "spy_sentinel", "file": "spy_signal_log.csv", "format": "score"},
    "QQQM": {"repo": "qqqm_sentinel", "file": "qqqm_signal_log.csv", "format": "score"},
    "TQQQ": {"repo": "tqqq_sentinel", "file": "tqqq_signal_log.csv", "format": "score"},
    "ARKK": {"repo": "splg_sentinel", "file": "arkk_signal_log.csv", "format": "score"},
    "DIA": {"repo": "dia_sentinel", "file": "dia_signal_log.csv", "format": "score"},
    "IWM": {"repo": "iwm_sentinel", "file": "iwm_signal_log.csv", "format": "score"},
    "USMV": {"repo": "usmv_sentinel", "file": "usmv_signal_log.csv", "format": "score"},
    "NVDA": {"repo": "nvda_sentinel", "file": "nvda_signal_log.csv", "format": "score"},
    "AVGO": {"repo": "avgo_sentinel", "file": "avgo_signal_log.csv", "format": "score"},
    "MU": {"repo": "mu_sentinel", "file": "mu_signal_log.csv", "format": "score"},
    "SMH": {"repo": "smh_sentinel", "file": "smh_signal_log.csv", "format": "score"},
    "SOXX": {"repo": "soxx_sentinel", "file": "soxx_signal_log.csv", "format": "score"},
    "QTUM": {"repo": "qtum_sentinel", "file": "qtum_signal_log.csv", "format": "score"},
}

# Mismo criterio que capital_allocator.py — se repite acá (en vez de
# importarlo) porque este script puede correr sin Alpaca configurado.
TIER_OF = {
    "QQQ": "core",
    "SPY": "core",
    "QQQM": "satellite_proven",
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    symbol TEXT NOT NULL,
    order_id TEXT,
    trade_date TEXT,
    buy_price REAL,
    sell_price REAL,
    qty REAL,
    pnl REAL,
    UNIQUE(symbol, order_id, trade_date, buy_price, sell_price, qty)
);

CREATE TABLE IF NOT EXISTS signal_history (
    symbol TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    price REAL,
    target_exposure_pct REAL,
    score REAL,
    regime TEXT,
    v5_active INTEGER,
    bear_confirmed INTEGER,
    changed INTEGER,
    trend REAL,
    momentum REAL,
    volatility REAL,
    volume REAL,
    quality REAL,
    rsi REAL,
    adx REAL,
    atr_pct REAL,
    roc20 REAL,
    roc60 REAL,
    drawdown REAL,
    UNIQUE(symbol, signal_date)
);

CREATE TABLE IF NOT EXISTS positions_snapshot (
    symbol TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    has_position INTEGER,
    qty REAL,
    avg_entry_price REAL,
    current_price REAL,
    market_value REAL,
    unrealized_pl REAL,
    unrealized_plpc REAL,
    signal_date TEXT,
    target_exposure_pct REAL,
    last_executed_target_pct REAL,
    pending_rebalance INTEGER,
    last_action TEXT,
    suspended INTEGER
);

CREATE TABLE IF NOT EXISTS performance_snapshot (
    symbol TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    realized_pnl REAL,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate REAL,
    avg_pnl_per_trade REAL
);

CREATE TABLE IF NOT EXISTS capital_allocation_snapshot (
    symbol TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    tier TEXT,
    allocation_pct REAL,
    allocation_usd REAL,
    total_capital REAL
);

-- Cada 50 operaciones cerradas de un bot toca hacer el análisis de
-- estrategia (backtest + re-tuning si corresponde), igual al que se
-- hizo el 2026-08-18 para QQQM/TQQQ/SPY/QQQ. baseline_trade_count es
-- el total_trades que tenía el símbolo la última vez que se hizo ese
-- análisis; trades_since = total_trades actual - baseline. Cuando se
-- hace el análisis hay que llamar a mark_analysis_done(symbol) para
-- resetear el contador.
CREATE TABLE IF NOT EXISTS analysis_checkpoints (
    symbol TEXT PRIMARY KEY,
    baseline_trade_count INTEGER NOT NULL,
    last_analysis_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_history_symbol ON signal_history(symbol, signal_date);
CREATE INDEX IF NOT EXISTS idx_positions_snapshot_symbol ON positions_snapshot(symbol, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_performance_snapshot_symbol ON performance_snapshot(symbol, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_capital_snapshot_symbol ON capital_allocation_snapshot(symbol, snapshot_at);
"""


def safe_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_csv_rows(repo, filename):
    if not GITHUB_TOKEN:
        print(f"⚠️ BOTS_READ_TOKEN no configurado, omitiendo {repo}/{filename}")
        return []

    url = f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.raw+json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"⚠️ Error leyendo {repo}/{filename}: HTTP {response.status_code}")
            return []
        return list(csv.DictReader(io.StringIO(response.text)))
    except Exception as e:
        print(f"⚠️ Error leyendo {repo}/{filename}: {e}")
        return []


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def import_trades(conn, performance_data):
    cur = conn.cursor()
    inserted = 0

    for symbol, data in performance_data.items():
        for trade in data.get("trades", []):
            cur.execute(
                """
                INSERT OR IGNORE INTO trades
                    (symbol, order_id, trade_date, buy_price, sell_price, qty, pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    trade.get("order_id"),
                    trade.get("date"),
                    safe_float(trade.get("buy_price")),
                    safe_float(trade.get("sell_price")),
                    safe_float(trade.get("qty")),
                    safe_float(trade.get("pnl")),
                ),
            )
            inserted += cur.rowcount

    conn.commit()
    print(f"✅ trades: {inserted} filas nuevas")


def import_nyse_scanner_trades(conn):
    """El NYSE Scanner opera un símbolo variable (no fijo), así que no
    tiene una entrada en SIGNAL_LOGS/performance.json como el resto --
    sus operaciones cerradas se leen directo de su propio
    state/trade_log.csv (ver execute_position.py) y se insertan en la
    misma tabla `trades`, reusando el esquema existente."""
    cur = conn.cursor()
    inserted = 0
    rows = fetch_csv_rows("nyse_scanner_sentinel", "state/trade_log.csv")

    for row in rows:
        symbol = row.get("symbol")
        if not symbol:
            continue
        order_id = f"nyse-{row.get('entry_date')}-{symbol}"
        cur.execute(
            """
            INSERT OR IGNORE INTO trades
                (symbol, order_id, trade_date, buy_price, sell_price, qty, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                order_id,
                row.get("exit_date"),
                safe_float(row.get("entry_price")),
                safe_float(row.get("exit_price")),
                safe_float(row.get("qty")),
                safe_float(row.get("pnl_usd")),
            ),
        )
        inserted += cur.rowcount

    conn.commit()
    print(f"✅ trades (NYSE Scanner): {inserted} filas nuevas")


def import_signal_history(conn):
    cur = conn.cursor()
    inserted = 0

    for symbol, cfg in SIGNAL_LOGS.items():
        rows = fetch_csv_rows(cfg["repo"], cfg["file"])

        for row in rows:
            if cfg["format"] == "v5":
                cur.execute(
                    """
                    INSERT OR IGNORE INTO signal_history
                        (symbol, signal_date, price, target_exposure_pct,
                         v5_active, bear_confirmed, changed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        row.get("date"),
                        safe_float(row.get("close")),
                        safe_float(row.get("target_exposure")),
                        row.get("v5_active") == "True",
                        row.get("bear_confirmed") == "True",
                        row.get("changed") == "True",
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO signal_history
                        (symbol, signal_date, price, target_exposure_pct, score, regime,
                         trend, momentum, volatility, volume, quality,
                         rsi, adx, atr_pct, roc20, roc60, drawdown)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        row.get("date"),
                        safe_float(row.get("price")),
                        safe_float(row.get("target_exposure_pct")),
                        safe_float(row.get("score")),
                        row.get("regime") or None,
                        safe_float(row.get("trend")),
                        safe_float(row.get("momentum")),
                        safe_float(row.get("volatility")),
                        safe_float(row.get("volume")),
                        safe_float(row.get("quality")),
                        safe_float(row.get("rsi")),
                        safe_float(row.get("adx")),
                        safe_float(row.get("atr_pct")),
                        safe_float(row.get("roc20")),
                        safe_float(row.get("roc60")),
                        safe_float(row.get("drawdown")),
                    ),
                )
            inserted += cur.rowcount

        print(f"  {symbol}: {len(rows)} filas leídas de {cfg['repo']}/{cfg['file']}")

    conn.commit()
    print(f"✅ signal_history: {inserted} filas nuevas")


def import_snapshots(conn, positions_data, performance_data, allocation_data):
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.cursor()

    for symbol, entry in positions_data.items():
        pos = entry.get("position", {})
        sig = entry.get("signal", {})
        cur.execute(
            """
            INSERT INTO positions_snapshot
                (symbol, snapshot_at, has_position, qty, avg_entry_price, current_price,
                 market_value, unrealized_pl, unrealized_plpc, signal_date,
                 target_exposure_pct, last_executed_target_pct, pending_rebalance,
                 last_action, suspended)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol, now,
                pos.get("has_position", False),
                pos.get("qty", 0), pos.get("avg_entry_price", 0), pos.get("current_price", 0),
                pos.get("market_value", 0), pos.get("unrealized_pl", 0), pos.get("unrealized_plpc", 0),
                sig.get("signal_date"), sig.get("target_exposure_pct"),
                sig.get("last_executed_target_pct"), sig.get("pending_rebalance", False),
                sig.get("last_action"), entry.get("suspended", False),
            ),
        )

    for symbol, data in performance_data.items():
        cur.execute(
            """
            INSERT INTO performance_snapshot
                (symbol, snapshot_at, realized_pnl, total_trades, winning_trades,
                 losing_trades, win_rate, avg_pnl_per_trade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol, now,
                data.get("realized_pnl"), data.get("total_trades"), data.get("winning_trades"),
                data.get("losing_trades"), data.get("win_rate"), data.get("avg_pnl_per_trade"),
            ),
        )

    total_capital = allocation_data.get("total_capital")
    allocation_usd = allocation_data.get("allocation_usd", {})
    for symbol, pct in allocation_data.get("allocation_pct", {}).items():
        cur.execute(
            """
            INSERT INTO capital_allocation_snapshot
                (symbol, snapshot_at, tier, allocation_pct, allocation_usd, total_capital)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol, now, TIER_OF.get(symbol), pct, allocation_usd.get(symbol), total_capital),
        )

    conn.commit()
    print("✅ snapshots (positions/performance/capital_allocation): 1 fila nueva por símbolo")


def load_json(filepath):
    path = Path(filepath)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


ANALYSIS_EVERY_N_TRADES = 50


def mark_analysis_done(symbol, db_file=DB_FILE):
    """Llamar después de terminar el análisis de estrategia de un
    símbolo (backtest + re-tuning si corresponde) para resetear su
    contador de 'operaciones desde el último análisis' a cero."""
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", (symbol,))
    current_count = cur.fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO analysis_checkpoints (symbol, baseline_trade_count, last_analysis_at)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            baseline_trade_count = excluded.baseline_trade_count,
            last_analysis_at = excluded.last_analysis_at
        """,
        (symbol, current_count, now),
    )
    conn.commit()
    conn.close()
    print(f"✅ Checkpoint de análisis reseteado para {symbol} en {current_count} operaciones")


def update_analysis_progress(conn):
    """Por símbolo: operaciones desde el último análisis de estrategia,
    y si ya tocó (>= ANALYSIS_EVERY_N_TRADES). Si un símbolo no tiene
    checkpoint todavía, arranca a contar desde su total actual (no
    desde cero absoluto) — no se le pide retroactivamente el análisis
    de operaciones que ya pasaron antes de que existiera este contador."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol FROM trades")
    symbols = [row[0] for row in cur.fetchall()]

    progress = {}
    for symbol in symbols:
        cur.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", (symbol,))
        current_count = cur.fetchone()[0]

        cur.execute(
            "SELECT baseline_trade_count, last_analysis_at FROM analysis_checkpoints WHERE symbol = ?",
            (symbol,),
        )
        row = cur.fetchone()

        if row is None:
            baseline, last_analysis_at = current_count, None
            cur.execute(
                "INSERT INTO analysis_checkpoints (symbol, baseline_trade_count, last_analysis_at) VALUES (?, ?, ?)",
                (symbol, baseline, None),
            )
        else:
            baseline, last_analysis_at = row

        trades_since = max(0, current_count - baseline)
        progress[symbol] = {
            "trades_since_analysis": trades_since,
            "trades_target": ANALYSIS_EVERY_N_TRADES,
            "analysis_due": trades_since >= ANALYSIS_EVERY_N_TRADES,
            "last_analysis_at": last_analysis_at,
        }

    conn.commit()

    with open("analysis_progress.json", "w") as f:
        json.dump(progress, f, indent=2)

    for symbol, p in progress.items():
        flag = " 🔔 TOCA ANÁLISIS" if p["analysis_due"] else ""
        print(f"  {symbol}: {p['trades_since_analysis']}/{p['trades_target']} operaciones{flag}")

    print("✅ analysis_progress.json guardado")


def main():
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)

    performance_data = load_json("performance.json")
    positions_data = load_json("positions.json")
    allocation_data = load_json("capital_allocation.json")

    import_trades(conn, performance_data)
    import_nyse_scanner_trades(conn)
    import_signal_history(conn)
    import_snapshots(conn, positions_data, performance_data, allocation_data)
    update_analysis_progress(conn)

    conn.close()
    print(f"✅ Base de datos actualizada: {DB_FILE}")


if __name__ == "__main__":
    main()
