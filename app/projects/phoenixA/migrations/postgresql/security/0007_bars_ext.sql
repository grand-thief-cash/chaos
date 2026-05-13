-- ============================================================
-- PhoenixA PostgreSQL Migration 0007: Bars Extension Tables
-- Target: chaos_db, schema: security_dev
-- Scope: bars_ext_baostock_stock_zh_a_daily
--
-- Extended indicators (valuation multiples) downloaded from
-- Baostock by Artemis, stored alongside the base OHLCV bars.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - bars_ext tables -> warm_storage (SATA, ~20 GB growing)
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- 1. bars_ext_baostock_stock_zh_a_daily
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bars_ext_baostock_stock_zh_a_daily (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    turn        DECIMAL(10,4),           -- 换手率(%)
    pe_ttm      DECIMAL(20,4),           -- 滚动市盈率
    ps_ttm      DECIMAL(20,4),           -- 滚动市销率
    pb_mrq      DECIMAL(20,4),           -- 市净率(MRQ)
    pcf_ncf_ttm DECIMAL(20,4),           -- 滚动市现率
    CONSTRAINT uk_bars_ext_baostock PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_beb_trade_date
    ON bars_ext_baostock_stock_zh_a_daily (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_beb_symbol
    ON bars_ext_baostock_stock_zh_a_daily (symbol) TABLESPACE warm_storage;
