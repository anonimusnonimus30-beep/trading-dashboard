#!/usr/bin/env python3
"""
Empuja telemetría detallada de todos los sentinels a Neon (Postgres).
Corre como paso extra del pipeline de update-dashboard.yml -- no
reemplaza sentinels.db (SQLite, sigue siendo la fuente rápida que lee
el propio dashboard), esto es la copia detallada y consultable con SQL
real desde afuera de GitHub Actions.

Cada función es independiente y atrapa sus propios errores: si Neon
está caído o una fuente puntual falla, el resto de la telemetría (y el
dashboard) sigue funcionando igual.
"""

import json
import os
from pathlib import Path

import psycopg2
import requests

from database import fetch_csv_rows, SIGNAL_LOGS, safe_float
from positions_analyzer import fetch_raw_json, BOTS as POSITION_BOTS

DATABASE_URL = os.getenv("DATABASE_URL")

# Cuenta1=FOT6 (derivados), cuenta2=N6ZG (QQQ+SPY).
ACCOUNTS = {
    "account1": (os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"), os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")),
    "account2": (os.getenv("SPY_APCA_API_KEY"), os.getenv("SPY_APCA_API_SECRET"), os.getenv("SPY_APCA_API_BASE_URL", "https://paper-api.alpaca.markets")),
}

# Registro estático de cada bot -- MAX_POSITION_PCT/stop-loss/risk_symbol
# vienen de los secrets/código de cada repo, se repiten acá a mano
# porque no cambian seguido y evita 11 llamadas extra a la API de
# GitHub solo para leer una constante.
BOTS_REGISTRY = {
    "QQQ":  dict(repo="qqq-sentinel",   account="account2", tier="core",              asset_type="etf",     max_position_pct=55, max_notional_usd=None, stop_loss_pct=-35, risk_symbol="QQQ"),
    "SPY":  dict(repo="spy_sentinel",   account="account2", tier="core",              asset_type="etf",     max_position_pct=45, max_notional_usd=None, stop_loss_pct=-30, risk_symbol="SPY"),
    "TQQQ": dict(repo="tqqq_sentinel",  account="account1", tier="satellite_proven",  asset_type="etf",     max_position_pct=3,    max_notional_usd=None, stop_loss_pct=-75, risk_symbol="QQQ"),
    "ARKK": dict(repo="splg_sentinel",  account="account1", tier="satellite_new",     asset_type="etf",     max_position_pct=1.5,  max_notional_usd=None, stop_loss_pct=-30, risk_symbol="QQQ"),
    "DIA":  dict(repo="dia_sentinel",   account="account1", tier="satellite_new",     asset_type="etf",     max_position_pct=1.5,  max_notional_usd=None, stop_loss_pct=-35, risk_symbol="SPY"),
    "IWM":  dict(repo="iwm_sentinel",   account="account1", tier="satellite_new",     asset_type="etf",     max_position_pct=1.5,  max_notional_usd=None, stop_loss_pct=-15, risk_symbol="SPY"),
    "USMV": dict(repo="usmv_sentinel",  account="account1", tier="satellite_new",     asset_type="etf",     max_position_pct=1.5,  max_notional_usd=None, stop_loss_pct=-30, risk_symbol="SPY"),
    "NVDA": dict(repo="nvda_sentinel",  account="account1", tier="satellite_stocks",  asset_type="stock",   max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-45, risk_symbol="QQQ"),
    "AVGO": dict(repo="avgo_sentinel",  account="account1", tier="satellite_stocks",  asset_type="stock",   max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-35, risk_symbol="QQQ"),
    "MU":   dict(repo="mu_sentinel",    account="account1", tier="satellite_stocks",  asset_type="stock",   max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-40, risk_symbol="QQQ"),
    "SMH":  dict(repo="smh_sentinel",   account="account1", tier="satellite_thematic", asset_type="etf",    max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-40, risk_symbol="QQQ"),
    "SOXX": dict(repo="soxx_sentinel",  account="account1", tier="satellite_thematic", asset_type="etf",    max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-35, risk_symbol="QQQ"),
    "QTUM": dict(repo="qtum_sentinel",  account="account1", tier="satellite_thematic", asset_type="etf",    max_position_pct=1.25, max_notional_usd=None, stop_loss_pct=-20, risk_symbol="QQQ"),
    "NYSE_SCANNER": dict(repo="nyse_scanner_sentinel", account="account1", tier="scanner", asset_type="scanner", max_position_pct=8, max_notional_usd=3000, stop_loss_pct=-8, risk_symbol=None),
}


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("Falta DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    # Las columnas son TIMESTAMPTZ (guardan el instante correcto en UTC
    # internamente, eso no cambia). Esto solo hace que CUALQUIER lectura
    # en esta conexión se muestre en hora de Ecuador en vez de UTC/GMT.
    # ALTER DATABASE/ROLE con el mismo timezone no alcanza acá porque el
    # pooler de Neon no lo propaga a conexiones nuevas -- hay que
    # setearlo explícito en cada sesión.
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'America/Guayaquil'")
    return conn


def seed_bots(conn):
    cur = conn.cursor()
    for symbol, cfg in BOTS_REGISTRY.items():
        cur.execute(
            """
            INSERT INTO bots (symbol, repo, account, tier, asset_type, max_position_pct, max_notional_usd, stop_loss_pct, risk_symbol)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                repo = EXCLUDED.repo, account = EXCLUDED.account, tier = EXCLUDED.tier,
                asset_type = EXCLUDED.asset_type, max_position_pct = EXCLUDED.max_position_pct,
                max_notional_usd = EXCLUDED.max_notional_usd, stop_loss_pct = EXCLUDED.stop_loss_pct,
                risk_symbol = EXCLUDED.risk_symbol
            """,
            (symbol, cfg["repo"], cfg["account"], cfg["tier"], cfg["asset_type"],
             cfg["max_position_pct"], cfg["max_notional_usd"], cfg["stop_loss_pct"], cfg["risk_symbol"]),
        )
    conn.commit()
    print(f"✅ Neon: bots registrados ({len(BOTS_REGISTRY)})")


def push_account_equity(conn):
    cur = conn.cursor()
    inserted = 0
    for account, (key, secret, base_url) in ACCOUNTS.items():
        if not key or not secret:
            continue
        try:
            r = requests.get(f"{base_url}/v2/account", headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=20)
            r.raise_for_status()
            acc = r.json()
        except Exception as e:
            print(f"⚠️ Neon: error consultando cuenta {account}: {e}")
            continue
        cur.execute(
            """INSERT INTO account_equity_snapshots (account, equity, cash, buying_power)
               VALUES (%s, %s, %s, %s)""",
            (account, safe_float(acc.get("equity")), safe_float(acc.get("cash")), safe_float(acc.get("buying_power"))),
        )
        inserted += 1
    conn.commit()
    print(f"✅ Neon: account_equity_snapshots +{inserted}")


def push_signals(conn):
    cur = conn.cursor()
    inserted = 0
    for symbol, cfg in SIGNAL_LOGS.items():
        rows = fetch_csv_rows(cfg["repo"], cfg["file"])
        for row in rows:
            try:
                if cfg["format"] == "v5":
                    cur.execute(
                        """INSERT INTO signals (symbol, signal_date, price, target_exposure_pct, v5_active, bear_confirmed)
                           VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (symbol, signal_date) DO NOTHING""",
                        (symbol, row.get("date"), safe_float(row.get("close")), safe_float(row.get("target_exposure")),
                         row.get("v5_active") == "True", row.get("bear_confirmed") == "True"),
                    )
                else:
                    cur.execute(
                        """INSERT INTO signals (symbol, signal_date, price, score, target_exposure_pct,
                               trend, momentum, volatility, volume, quality, rsi, adx, atr_pct, roc20, roc60, drawdown, regime)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (symbol, signal_date) DO NOTHING""",
                        (symbol, row.get("date"), safe_float(row.get("price")), safe_float(row.get("score")),
                         safe_float(row.get("target_exposure_pct")), safe_float(row.get("trend")), safe_float(row.get("momentum")),
                         safe_float(row.get("volatility")), safe_float(row.get("volume")), safe_float(row.get("quality")),
                         safe_float(row.get("rsi")), safe_float(row.get("adx")), safe_float(row.get("atr_pct")),
                         safe_float(row.get("roc20")), safe_float(row.get("roc60")), safe_float(row.get("drawdown")),
                         row.get("regime")),
                    )
                inserted += cur.rowcount
            except Exception as e:
                print(f"⚠️ Neon: fila de señal descartada ({symbol}, {row.get('date')}): {e}")
                conn.rollback()
    conn.commit()
    print(f"✅ Neon: signals +{inserted}")


def push_nyse_scanner_signals(conn):
    cur = conn.cursor()
    inserted = 0
    rows = fetch_csv_rows("nyse_scanner_sentinel", "state/signal_log.csv")
    for row in rows:
        try:
            cur.execute(
                """INSERT INTO nyse_scanner_signals (signal_date, ticker, score, price, roc63, roc126, breakout20, volume_surge, vol_contraction)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (signal_date, ticker) DO NOTHING""",
                (row.get("date"), row.get("symbol"), safe_float(row.get("score")), safe_float(row.get("price")),
                 safe_float(row.get("roc63")), safe_float(row.get("roc126")),
                 row.get("breakout20") == "True", row.get("volume_surge") == "True", row.get("vol_contraction") == "True"),
            )
            inserted += cur.rowcount
        except Exception as e:
            print(f"⚠️ Neon: fila del scanner descartada ({row.get('date')}, {row.get('symbol')}): {e}")
            conn.rollback()
    conn.commit()
    print(f"✅ Neon: nyse_scanner_signals +{inserted}")


def push_positions(conn, positions_data, nyse_scanner_data):
    cur = conn.cursor()
    inserted = 0
    for symbol, entry in positions_data.items():
        pos = entry.get("position", {})
        sig = entry.get("signal", {})
        cur.execute(
            """INSERT INTO positions_snapshots
                   (symbol, bot_symbol, has_position, qty, avg_entry_price, current_price,
                    market_value, unrealized_pl, unrealized_plpc, signal_target_pct, executed_target_pct, pending_rebalance)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (symbol, symbol, pos.get("has_position", False), safe_float(pos.get("qty")), safe_float(pos.get("avg_entry_price")),
             safe_float(pos.get("current_price")), safe_float(pos.get("market_value")), safe_float(pos.get("unrealized_pl")),
             safe_float(pos.get("unrealized_plpc")), safe_float(sig.get("target_exposure_pct")),
             safe_float(sig.get("last_executed_target_pct")), bool(sig.get("pending_rebalance"))),
        )
        inserted += 1

    if nyse_scanner_data and nyse_scanner_data.get("status") == "in_position":
        pos = nyse_scanner_data.get("position") or {}
        cur.execute(
            """INSERT INTO positions_snapshots
                   (symbol, bot_symbol, has_position, qty, current_price, market_value, unrealized_pl, unrealized_plpc)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (nyse_scanner_data.get("symbol"), "NYSE_SCANNER", True, safe_float(pos.get("qty")),
             safe_float(pos.get("current_price")), safe_float(pos.get("market_value")),
             safe_float(pos.get("unrealized_pl")), safe_float(pos.get("unrealized_plpc"))),
        )
        inserted += 1

    conn.commit()
    print(f"✅ Neon: positions_snapshots +{inserted}")


def push_news_sentiment(conn):
    cur = conn.cursor()
    inserted = 0
    for symbol, cfg in POSITION_BOTS.items():
        data = fetch_raw_json(cfg["repo"], "news_sentiment.json")
        if not data:
            continue
        own = data.get(symbol, {})
        macro = data.get("macro", {})
        top_articles = own.get("top_articles") or []
        top = top_articles[0] if top_articles else {}
        try:
            cur.execute(
                """INSERT INTO news_sentiment_snapshots
                       (symbol, sentiment_score, articles_analyzed, bullish_count, bearish_count, neutral_count,
                        top_article_title, top_article_source, top_article_sentiment, macro_sentiment_score)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (symbol, safe_float(own.get("sentiment_score")), own.get("articles_analyzed"),
                 own.get("bullish_count"), own.get("bearish_count"), own.get("neutral_count"),
                 top.get("title"), top.get("source"), safe_float(top.get("sentiment")),
                 safe_float(macro.get("sentiment_score"))),
            )
            inserted += 1
        except Exception as e:
            print(f"⚠️ Neon: sentimiento descartado ({symbol}): {e}")
            conn.rollback()
    conn.commit()
    print(f"✅ Neon: news_sentiment_snapshots +{inserted}")


def push_closed_trades(conn, performance_data):
    cur = conn.cursor()
    inserted = 0
    for symbol, data in performance_data.items():
        for trade in data.get("trades", []):
            try:
                cur.execute(
                    """INSERT INTO closed_trades (bot_symbol, traded_symbol, order_id, exit_date, buy_price, sell_price, qty, pnl_usd)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (bot_symbol, traded_symbol, order_id, entry_date, buy_price, sell_price, qty) DO NOTHING""",
                    (symbol, symbol, trade.get("order_id"), trade.get("date"),
                     safe_float(trade.get("buy_price")), safe_float(trade.get("sell_price")),
                     safe_float(trade.get("qty")), safe_float(trade.get("pnl"))),
                )
                inserted += cur.rowcount
            except Exception as e:
                print(f"⚠️ Neon: trade descartado ({symbol}): {e}")
                conn.rollback()

    nyse_trades = fetch_csv_rows("nyse_scanner_sentinel", "state/trade_log.csv")
    for t in nyse_trades:
        symbol = t.get("symbol")
        if not symbol:
            continue
        try:
            cur.execute(
                """INSERT INTO closed_trades (bot_symbol, traded_symbol, order_id, entry_date, exit_date,
                       buy_price, sell_price, qty, pnl_usd, pnl_pct, exit_reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (bot_symbol, traded_symbol, order_id, entry_date, buy_price, sell_price, qty) DO NOTHING""",
                ("NYSE_SCANNER", symbol, f"nyse-{t.get('entry_date')}-{symbol}", t.get("entry_date"), t.get("exit_date"),
                 safe_float(t.get("entry_price")), safe_float(t.get("exit_price")), safe_float(t.get("qty")),
                 safe_float(t.get("pnl_usd")), safe_float(t.get("pnl_pct")), t.get("exit_reason")),
            )
            inserted += cur.rowcount
        except Exception as e:
            print(f"⚠️ Neon: trade del scanner descartado: {e}")
            conn.rollback()

    conn.commit()
    print(f"✅ Neon: closed_trades +{inserted}")


def push_capital_allocation(conn, allocation_data):
    cur = conn.cursor()
    inserted = 0
    total_capital = safe_float(allocation_data.get("total_capital"))
    allocation_pct = allocation_data.get("allocation_pct", {})
    allocation_usd = allocation_data.get("allocation_usd", {})
    for symbol, pct in allocation_pct.items():
        tier = BOTS_REGISTRY.get(symbol, {}).get("tier")
        cur.execute(
            """INSERT INTO capital_allocation_snapshots (symbol, tier, allocation_pct, allocation_usd, total_capital)
               VALUES (%s, %s, %s, %s, %s)""",
            (symbol, tier, safe_float(pct), safe_float(allocation_usd.get(symbol)), total_capital),
        )
        inserted += 1
    conn.commit()
    print(f"✅ Neon: capital_allocation_snapshots +{inserted}")


def push_stop_loss_events(conn):
    cur = conn.cursor()
    inserted = 0
    for symbol, cfg in POSITION_BOTS.items():
        exec_state = fetch_raw_json(cfg["repo"], cfg["execution_file"])
        if not exec_state:
            continue
        stop = exec_state.get("last_stop_loss")
        if not stop:
            continue
        try:
            cur.execute(
                """INSERT INTO stop_loss_events (symbol, signal_date, drawdown_pct, threshold_pct, qty_sold, dry_run)
                   SELECT %s, %s, %s, %s, %s, %s
                   WHERE NOT EXISTS (
                       SELECT 1 FROM stop_loss_events
                       WHERE symbol = %s AND signal_date = %s AND drawdown_pct = %s
                   )""",
                (symbol, stop.get("date"), safe_float(stop.get("drawdown_pct")),
                 BOTS_REGISTRY.get(symbol, {}).get("stop_loss_pct"), safe_float(stop.get("qty_sold")),
                 stop.get("action") == "dry_run",
                 symbol, stop.get("date"), safe_float(stop.get("drawdown_pct"))),
            )
            inserted += cur.rowcount
        except Exception as e:
            print(f"⚠️ Neon: evento de stop-loss descartado ({symbol}): {e}")
            conn.rollback()
    conn.commit()
    print(f"✅ Neon: stop_loss_events +{inserted}")


def run(positions_data=None, performance_data=None, allocation_data=None, nyse_scanner_data=None):
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL no configurado, se omite la telemetría a Neon.")
        return

    try:
        conn = get_conn()
    except Exception as e:
        print(f"⚠️ Neon: no se pudo conectar ({e}), se omite esta corrida.")
        return

    for label, fn, args in [
        ("seed_bots", seed_bots, ()),
        ("account_equity", push_account_equity, ()),
        ("signals", push_signals, ()),
        ("nyse_scanner_signals", push_nyse_scanner_signals, ()),
        ("positions", push_positions, (positions_data or {}, nyse_scanner_data or {})),
        ("news_sentiment", push_news_sentiment, ()),
        ("closed_trades", push_closed_trades, (performance_data or {},)),
        ("capital_allocation", push_capital_allocation, (allocation_data or {},)),
        ("stop_loss_events", push_stop_loss_events, ()),
    ]:
        try:
            fn(conn, *args)
        except Exception as e:
            print(f"⚠️ Neon: falló {label}: {e}")
            conn.rollback()

    conn.close()


if __name__ == "__main__":
    def _load(path):
        p = Path(path)
        return json.loads(p.read_text()) if p.exists() else {}

    run(
        positions_data=_load("positions.json"),
        performance_data=_load("performance.json"),
        allocation_data=_load("capital_allocation.json"),
        nyse_scanner_data=_load("nyse_scanner.json"),
    )
