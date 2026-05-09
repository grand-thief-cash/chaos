-- ============================================================
-- PhoenixA PostgreSQL Migration 0001: Taxonomy & Industry Tables
-- Target: chaos_db, schema: security_dev
-- Scope: taxonomy_category, taxonomy_security_map,
--        industry_constituent, industry_weight, industry_daily
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - taxonomy_category / taxonomy_security_map  -> pg_default (NVMe, small metadata)
--   - industry_constituent / industry_weight / industry_daily -> warm_storage (SATA, business data)
--
-- JSONB advantages leveraged:
--   - GIN index on attrs_json for fast @>, ?, ?| queries
--   - Native jsonb operators available for ad-hoc filtering
-- ============================================================

-- 1. taxonomy_category
CREATE TABLE IF NOT EXISTS taxonomy_category (
    id           BIGSERIAL      PRIMARY KEY,
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    code         VARCHAR(64)    NOT NULL,
    name         VARCHAR(255)   NOT NULL,
    parent_code  VARCHAR(64),
    index_code   VARCHAR(64),
    level        SMALLINT       NOT NULL DEFAULT 0,
    is_leaf      BOOLEAN        NOT NULL DEFAULT TRUE,
    attrs_json   JSONB,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_src_tax_mkt_code UNIQUE (source, taxonomy, market, code)
) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_tc_parent ON taxonomy_category (source, taxonomy, market, parent_code);
CREATE INDEX IF NOT EXISTS idx_tc_level ON taxonomy_category (source, taxonomy, market, level);
CREATE INDEX IF NOT EXISTS idx_tc_index_code ON taxonomy_category (source, taxonomy, index_code);
-- JSONB GIN index: enables fast @>, ?, ?| queries on attrs_json
-- e.g. WHERE attrs_json @> '{"is_pub": 1}'
-- e.g. WHERE attrs_json ? 'change_reason'
CREATE INDEX IF NOT EXISTS idx_tc_attrs_gin ON taxonomy_category USING GIN (attrs_json);

-- 2. taxonomy_security_map
CREATE TABLE IF NOT EXISTS taxonomy_security_map (
    source        VARCHAR(32) NOT NULL,
    taxonomy      VARCHAR(32) NOT NULL,
    category_code VARCHAR(64) NOT NULL,
    symbol        VARCHAR(32) NOT NULL,
    asset_type    VARCHAR(16) NOT NULL DEFAULT 'stock',
    market        VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    CONSTRAINT uk_src_tax_cat_sec UNIQUE (source, taxonomy, category_code, symbol, asset_type, market)
) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_tsm_symbol ON taxonomy_security_map (symbol, asset_type, market);
CREATE INDEX IF NOT EXISTS idx_tsm_category ON taxonomy_security_map (source, taxonomy, category_code);

-- 3. industry_constituent
CREATE TABLE IF NOT EXISTS industry_constituent (
    id           BIGSERIAL      PRIMARY KEY,
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    index_code   VARCHAR(64)    NOT NULL,
    con_code     VARCHAR(64)    NOT NULL DEFAULT '',
    symbol       VARCHAR(32)    NOT NULL,
    index_name   VARCHAR(255)   NOT NULL DEFAULT '',
    in_date      VARCHAR(10),
    out_date     VARCHAR(10),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_src_tax_idx_sym UNIQUE (source, taxonomy, index_code, symbol, market)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_ic_index_code ON industry_constituent (source, taxonomy, index_code) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_ic_symbol ON industry_constituent (symbol, market) TABLESPACE warm_storage;

-- 4. industry_weight
CREATE TABLE IF NOT EXISTS industry_weight (
    id           BIGSERIAL      PRIMARY KEY,
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    index_code   VARCHAR(64)    NOT NULL,
    con_code     VARCHAR(64)    NOT NULL DEFAULT '',
    symbol       VARCHAR(32)    NOT NULL,
    trade_date   VARCHAR(10)    NOT NULL,
    weight       NUMERIC(10,6),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_src_tax_idx_sym_dt UNIQUE (source, taxonomy, index_code, symbol, market, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_iw_index_date ON industry_weight (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_iw_symbol_date ON industry_weight (symbol, market, trade_date) TABLESPACE warm_storage;

-- 5. industry_daily
CREATE TABLE IF NOT EXISTS industry_daily (
    id           BIGSERIAL      PRIMARY KEY,
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    index_code   VARCHAR(64)    NOT NULL,
    trade_date   VARCHAR(10)    NOT NULL,
    open         NUMERIC(20,4),
    high         NUMERIC(20,4),
    close        NUMERIC(20,4),
    low          NUMERIC(20,4),
    pre_close    NUMERIC(20,4),
    amount       NUMERIC(20,4),
    volume       NUMERIC(20,4),
    pb           NUMERIC(20,4),
    pe           NUMERIC(20,4),
    total_cap    NUMERIC(20,4),
    a_float_cap  NUMERIC(20,4),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_src_tax_idx_mkt_dt UNIQUE (source, taxonomy, index_code, market, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_id_index_date ON industry_daily (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_id_trade_date ON industry_daily (source, taxonomy, trade_date) TABLESPACE warm_storage;
