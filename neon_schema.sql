-- Telemetría detallada de todos los sentinels en Neon (Postgres).
-- Complementa (no reemplaza) sentinels.db (SQLite, liviana, vive en
-- el repo) con historial más rico y consultable con SQL real desde
-- fuera de GitHub Actions.

CREATE TABLE IF NOT EXISTS bots (
    symbol TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    account TEXT NOT NULL,           -- 'account1' (FOT6) | 'account2' (N6ZG)
    tier TEXT,                       -- core | satellite_proven | satellite_new | satellite_stocks | scanner
    asset_type TEXT,                 -- 'etf' | 'stock' | 'scanner'
    max_position_pct REAL,
    max_notional_usd REAL,
    stop_loss_pct REAL,
    risk_symbol TEXT,                -- a qué índice se referencia en risk_gate.py (QQQ/SPY)
    created_at TIMESTAMPTZ DEFAULT now(),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS account_equity_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    equity REAL,
    cash REAL,
    buying_power REAL,
    UNIQUE(account, snapshot_at)
);

-- Cada fila = una corrida de generate_signal.py de un bot. Guarda el
-- score y TODOS los componentes que haya disponibles (no todos los
-- bots calculan los mismos -- TQQQ tiene régimen y penalties propios,
-- el resto trend/momentum/volatility/volume/quality).
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES bots(symbol),
    signal_date DATE NOT NULL,
    price REAL,
    score REAL,
    target_exposure_pct REAL,
    regime TEXT,                     -- solo TQQQ (BEAR/BULL/STRONG_BULL/HIGH_VOL/...)
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
    v5_active BOOLEAN,                -- solo QQQ
    bear_confirmed BOOLEAN,           -- solo QQQ
    ingested_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol, signal_date)
);

-- Señales cross-sectional del NYSE Scanner: una fila por (día, ticker
-- candidato con score >= umbral) -- no es "el bot X", es todo el
-- universo evaluado ese día.
CREATE TABLE IF NOT EXISTS nyse_scanner_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    score REAL,
    price REAL,
    roc63 REAL,
    roc126 REAL,
    breakout20 BOOLEAN,
    volume_surge BOOLEAN,
    vol_contraction BOOLEAN,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(signal_date, ticker)
);

CREATE TABLE IF NOT EXISTS positions_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,             -- para NYSE Scanner: el ticker en posición ese día, si hay
    bot_symbol TEXT NOT NULL,         -- el bot dueño ('NYSE_SCANNER' para el scanner, el símbolo mismo para el resto)
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    has_position BOOLEAN,
    qty REAL,
    avg_entry_price REAL,
    current_price REAL,
    market_value REAL,
    unrealized_pl REAL,
    unrealized_plpc REAL,
    signal_target_pct REAL,
    executed_target_pct REAL,
    pending_rebalance BOOLEAN
);

CREATE TABLE IF NOT EXISTS news_sentiment_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sentiment_score REAL,
    articles_analyzed INTEGER,
    bullish_count INTEGER,
    bearish_count INTEGER,
    neutral_count INTEGER,
    top_article_title TEXT,
    top_article_source TEXT,
    top_article_sentiment REAL,
    exposure_multiplier REAL,
    macro_sentiment_score REAL
);

-- Operaciones CERRADAS (round-trip), unificado para toda la familia
-- incluido el NYSE Scanner (que usa order_id sintético "nyse-...").
CREATE TABLE IF NOT EXISTS closed_trades (
    id BIGSERIAL PRIMARY KEY,
    bot_symbol TEXT NOT NULL,          -- dueño de la operación ('NYSE_SCANNER' o el símbolo del bot)
    traded_symbol TEXT NOT NULL,       -- qué se compró/vendió (== bot_symbol salvo NYSE Scanner)
    order_id TEXT,
    entry_date DATE,
    exit_date DATE,
    buy_price REAL,
    sell_price REAL,
    qty REAL,
    pnl_usd REAL,
    pnl_pct REAL,
    exit_reason TEXT,                  -- 'stop' | 'target' | 'horizonte' | null (resto de la familia)
    UNIQUE(bot_symbol, traded_symbol, order_id, entry_date, buy_price, sell_price, qty)
);

CREATE TABLE IF NOT EXISTS capital_allocation_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tier TEXT,
    allocation_pct REAL,
    allocation_usd REAL,
    total_capital REAL
);

-- Cada vez que se dispara el freno de emergencia (stop-loss ancho) de
-- un bot -- separado de closed_trades porque acá el interés es el
-- EVENTO de riesgo en sí (drawdown que lo gatilló), no solo el P&L.
CREATE TABLE IF NOT EXISTS stop_loss_events (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    signal_date DATE,
    drawdown_pct REAL,
    threshold_pct REAL,
    qty_sold REAL,
    dry_run BOOLEAN
);

-- Historial de cuándo y cómo se validó (backtest + train/test) el
-- motor de cada bot -- para no perder el rastro de POR QUÉ están los
-- parámetros actuales, algo que hasta ahora solo vivía en comentarios
-- de scoring.py de cada repo.
CREATE TABLE IF NOT EXISTS backtest_validations (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    validated_at DATE NOT NULL,
    method TEXT,                       -- p.ej. 'grid_search_4_split_train_test'
    tiers TEXT,                        -- '90/75/55/35'
    stop_loss_pct REAL,
    deadzone_pct REAL,
    win_rate_oos REAL,                 -- win rate promedio fuera de muestra
    cagr_oos REAL,
    max_dd_oos REAL,
    buy_hold_win_rate REAL,
    buy_hold_cagr REAL,
    buy_hold_max_dd REAL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_date ON signals(symbol, signal_date);
CREATE INDEX IF NOT EXISTS idx_nyse_signals_date ON nyse_scanner_signals(signal_date);
CREATE INDEX IF NOT EXISTS idx_positions_symbol_time ON positions_snapshots(bot_symbol, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_news_symbol_time ON news_sentiment_snapshots(symbol, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_trades_bot ON closed_trades(bot_symbol, exit_date);
CREATE INDEX IF NOT EXISTS idx_capital_symbol_time ON capital_allocation_snapshots(symbol, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_stop_events_symbol ON stop_loss_events(symbol, triggered_at);
CREATE INDEX IF NOT EXISTS idx_equity_account_time ON account_equity_snapshots(account, snapshot_at);
