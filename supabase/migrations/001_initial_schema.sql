-- AEGIS AI Quant — Supabase PostgreSQL Migration
-- Migrated from SQLite (23 tables, 20 indexes)

-- ============================================================
-- POSITIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    average_price REAL NOT NULL
);

-- ============================================================
-- PAPER ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_orders (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    reference_price REAL NOT NULL,
    notional REAL NOT NULL,
    status TEXT NOT NULL,
    strategy TEXT DEFAULT 'manual',
    mode TEXT DEFAULT 'paper',
    exchange_order_id TEXT,
    fill_price REAL,
    fee REAL DEFAULT 0,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paper_orders_created ON paper_orders (created_at DESC);

-- ============================================================
-- MARKET SNAPSHOTS
-- ============================================================
CREATE TABLE IF NOT EXISTS market_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_collected_at ON market_snapshots (symbol, collected_at DESC);

-- ============================================================
-- OHLCV CANDLES
-- ============================================================
CREATE TABLE IF NOT EXISTS ohlcv_candles (
    symbol TEXT NOT NULL,
    "interval" TEXT NOT NULL,
    open_time BIGINT NOT NULL,
    close_time BIGINT NOT NULL,
    "open" REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    "close" REAL NOT NULL,
    volume REAL NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, "interval", open_time)
);

-- ============================================================
-- BACKTESTS
-- ============================================================
CREATE TABLE IF NOT EXISTS backtests (
    id BIGSERIAL PRIMARY KEY,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    "interval" TEXT NOT NULL,
    parameters_json JSONB NOT NULL,
    metrics_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests (strategy);
CREATE INDEX IF NOT EXISTS idx_backtests_created ON backtests (created_at DESC);

-- ============================================================
-- DECISION JOURNAL
-- ============================================================
CREATE TABLE IF NOT EXISTS decision_journal (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    "interval" TEXT NOT NULL,
    decision_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decision_journal_created ON decision_journal (created_at DESC);

-- ============================================================
-- SYSTEM CONTROLS
-- ============================================================
CREATE TABLE IF NOT EXISTS system_controls (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- SYSTEM ALERTS
-- ============================================================
CREATE TABLE IF NOT EXISTS system_alerts (
    id BIGSERIAL PRIMARY KEY,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_system_alerts_created ON system_alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts (severity);

-- ============================================================
-- FEAR & GREED
-- ============================================================
CREATE TABLE IF NOT EXISTS fear_greed (
    id BIGSERIAL PRIMARY KEY,
    value INTEGER NOT NULL,
    classification TEXT NOT NULL,
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- FUNDING RATES
-- ============================================================
CREATE TABLE IF NOT EXISTS funding_rates (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    mark_price REAL NOT NULL,
    index_price REAL NOT NULL,
    funding_rate REAL NOT NULL,
    next_funding_time BIGINT NOT NULL,
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_funding_rates_symbol_collected_at ON funding_rates (symbol, collected_at DESC);

-- ============================================================
-- OPEN INTEREST
-- ============================================================
CREATE TABLE IF NOT EXISTS open_interest (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    open_interest REAL NOT NULL,
    open_interest_usd REAL NOT NULL,
    price REAL NOT NULL,
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_open_interest_symbol_collected_at ON open_interest (symbol, collected_at DESC);

-- ============================================================
-- MEMORY EPISODES
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_episodes (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    features_json JSONB NOT NULL,
    result_json JSONB,
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_fingerprint ON memory_episodes (fingerprint);
CREATE INDEX IF NOT EXISTS idx_memory_symbol_strategy ON memory_episodes (symbol, strategy);

-- ============================================================
-- ICT TRADES JOURNAL
-- ============================================================
CREATE TABLE IF NOT EXISTS ict_trades_journal (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    setup TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    entry_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    tp_price REAL NOT NULL,
    risk_amount REAL NOT NULL,
    result TEXT NOT NULL,
    rr_ratio REAL NOT NULL,
    drawdown REAL,
    pnl REAL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ict_journal_date ON ict_trades_journal (date DESC);
CREATE INDEX IF NOT EXISTS idx_ict_journal_instrument ON ict_trades_journal (instrument);
CREATE INDEX IF NOT EXISTS idx_ict_journal_result ON ict_trades_journal (result);

-- ============================================================
-- ENGINE STATE
-- ============================================================
CREATE TABLE IF NOT EXISTS engine_state (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- ENGINE LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS engine_log (
    id BIGSERIAL PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json JSONB,
    severity TEXT NOT NULL DEFAULT 'info',
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_engine_log_cycle ON engine_log (cycle_id);
CREATE INDEX IF NOT EXISTS idx_engine_log_created ON engine_log (created_at DESC);

-- ============================================================
-- TRAILING STOPS ACTIVE
-- ============================================================
CREATE TABLE IF NOT EXISTS trailing_stops_active (
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    trail_pct REAL NOT NULL,
    highest_price REAL,
    lowest_price REAL,
    stop_price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (symbol, side)
);

-- ============================================================
-- TRADE SIGNALS
-- ============================================================
CREATE TABLE IF NOT EXISTS trade_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_json JSONB NOT NULL,
    executed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trade_signals_created ON trade_signals (created_at DESC);

-- ============================================================
-- OPEN ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS open_orders (
    order_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    limit_price REAL NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- DEPLOYMENT PIPELINES
-- ============================================================
CREATE TABLE IF NOT EXISTS deployment_pipelines (
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    pipeline_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (strategy_id, symbol)
);

-- ============================================================
-- ML MODELS
-- ============================================================
CREATE TABLE IF NOT EXISTS ml_models (
    model_id TEXT PRIMARY KEY,
    model_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- STRATEGY STATS
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_stats (
    strategy_id TEXT PRIMARY KEY,
    stats_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- TRADE OUTCOMES
-- ============================================================
CREATE TABLE IF NOT EXISTS trade_outcomes (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity REAL NOT NULL,
    pnl REAL,
    pnl_pct REAL,
    duration_seconds INTEGER,
    regime_at_entry TEXT,
    features_json JSONB,
    status TEXT NOT NULL DEFAULT 'open',
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_trade_outcomes_strategy ON trade_outcomes (strategy);
CREATE INDEX IF NOT EXISTS idx_trade_outcomes_status ON trade_outcomes (status);
CREATE INDEX IF NOT EXISTS idx_trade_outcomes_opened ON trade_outcomes (opened_at DESC);

-- ============================================================
-- CIRCUIT BREAKER STATE (stored in system_controls)
-- ============================================================
-- Circuit breaker state is stored as a JSON blob in system_controls
-- No additional table needed.

-- ============================================================
-- DAILY REPORTS (stored in engine_log)
-- -- Daily reports are generated from engine_log events
-- No additional table needed.

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
-- Enable RLS on all tables
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE ohlcv_candles ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtests ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fear_greed ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_interest ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ict_trades_journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE engine_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE engine_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE trailing_stops_active ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_pipelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_outcomes ENABLE ROW LEVEL SECURITY;

-- Service role bypass (for backend)
CREATE POLICY "Service role full access" ON positions FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON paper_orders FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON market_snapshots FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON ohlcv_candles FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON backtests FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON decision_journal FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON system_controls FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON system_alerts FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON fear_greed FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON funding_rates FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON open_interest FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON memory_episodes FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON ict_trades_journal FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON engine_state FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON engine_log FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON trailing_stops_active FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON trade_signals FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON open_orders FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON deployment_pipelines FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON ml_models FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON strategy_stats FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON trade_outcomes FOR ALL USING (TRUE) WITH CHECK (TRUE);
