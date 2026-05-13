-- ============================================================
-- PhoenixA PostgreSQL Migration 0006: Daily Bars Tables
-- Target: chaos_db, schema: security_dev
-- Scope: bars_stock_zh_a_daily_nf, bars_stock_zh_a_daily_hfq,
--        bars_index_zh_a_daily_nf
--
-- OHLCV daily candlestick tables migrated from MySQL.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - all bars_daily tables -> warm_storage (SATA, ~42 GB growing)
--
-- TimescaleDB: these are hypertable candidates; once TimescaleDB
-- is installed, run the ALTER / create_hypertable commands in
-- the comment block at the bottom.
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- 1. bars_stock_zh_a_daily_nf  (A股日线不复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_nf (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    open        DECIMAL(20,4),
    high        DECIMAL(20,4),
    low         DECIMAL(20,4),
    close       DECIMAL(20,4),
    volume      BIGINT,
    amount      BIGINT,
    preclose    DECIMAL(20,4),
    pct_chg     DECIMAL(10,4),
    CONSTRAINT uk_bars_daily_nf PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bdnf_trade_date
    ON bars_stock_zh_a_daily_nf (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bdnf_symbol
    ON bars_stock_zh_a_daily_nf (symbol) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 2. bars_stock_zh_a_daily_hfq  (A股日线前复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_hfq (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    open        DECIMAL(20,4),
    high        DECIMAL(20,4),
    low         DECIMAL(20,4),
    close       DECIMAL(20,4),
    volume      BIGINT,
    amount      BIGINT,
    preclose    DECIMAL(20,4),
    pct_chg     DECIMAL(10,4),
    CONSTRAINT uk_bars_daily_hfq PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bdhfq_trade_date
    ON bars_stock_zh_a_daily_hfq (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bdhfq_symbol
    ON bars_stock_zh_a_daily_hfq (symbol) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 3. bars_index_zh_a_daily_nf  (A股指数日线不复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bars_index_zh_a_daily_nf (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    open        DECIMAL(20,4),
    high        DECIMAL(20,4),
    low         DECIMAL(20,4),
    close       DECIMAL(20,4),
    volume      BIGINT,
    amount      BIGINT,
    preclose    DECIMAL(20,4),
    pct_chg     DECIMAL(10,4),
    CONSTRAINT uk_bars_idx_daily_nf PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bidnf_trade_date
    ON bars_index_zh_a_daily_nf (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bidnf_symbol
    ON bars_index_zh_a_daily_nf (symbol) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- TimescaleDB hypertable conversion (run manually after
-- TimescaleDB extension is installed):
--
-- SELECT create_hypertable('bars_stock_zh_a_daily_nf',
--     'trade_date', chunk_time_interval => INTERVAL '1 year',
--     migrate_data => true);
-- ALTER TABLE bars_stock_zh_a_daily_nf SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'symbol',
--     timescaledb.compress_orderby = 'trade_date DESC'
-- );
-- SELECT add_compression_policy('bars_stock_zh_a_daily_nf',
--     INTERVAL '6 months');
--
-- Repeat for bars_stock_zh_a_daily_hfq and bars_index_zh_a_daily_nf.
-- ──────────────────────────────────────────────────────────
