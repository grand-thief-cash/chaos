-- ============================================================
-- PhoenixA PostgreSQL Migration 0005: Security Registry
-- Target: chaos_db, schema: security_dev
-- Scope: security_registry
--
-- Unified stock/index/ETF/futures/fund/cb registry — the
-- single source of truth for all security identifiers.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - security_registry -> pg_default (NVMe, <0.1 GB metadata)
-- ============================================================

-- 1. security_registry
CREATE TABLE IF NOT EXISTS security_registry (
    symbol       VARCHAR(32)    NOT NULL,
    asset_type   VARCHAR(16)    NOT NULL,        -- stock / index / etf / futures / fund / cb
    market       VARCHAR(16)    NOT NULL,         -- zh_a / hk / us / global
    exchange     VARCHAR(8)     NOT NULL,          -- SH / SZ / BJ / HKEX / NYSE / ...
    name         VARCHAR(128)   NOT NULL DEFAULT '',
    full_name    VARCHAR(256),
    status       VARCHAR(16)    NOT NULL DEFAULT 'active',  -- active / delisted / suspended
    list_date    DATE,
    delist_date  DATE,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_security_registry PRIMARY KEY (symbol, asset_type, market)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_sr_asset_market
    ON security_registry (asset_type, market);
CREATE INDEX IF NOT EXISTS idx_sr_exchange
    ON security_registry (exchange);
CREATE INDEX IF NOT EXISTS idx_sr_status
    ON security_registry (status)
    WHERE status != 'active';
