-- ============================================================
-- PhoenixA PostgreSQL Migration 0001: ODS layer (raw / source-faithful)
-- Layer: ods
-- Scope: taxonomy_category, taxonomy_security_map,
--        industry_constituent, industry_weight, industry_daily,
--        financial_statement, corporate_action,
--        bars_stock_zh_a_daily_nf, bars_stock_zh_a_daily_hfq,
--        bars_index_zh_a_daily_nf, bars_ext_baostock_stock_zh_a_daily,
--        adjust_factor, long_hu_bang, equity_structure, security_registry
--
-- ODS = external-source landing tables (downloaded by artemis from external
-- APIs and POSTed to phoenixA). Includes source-faithful tables (with a
-- `source` column) and the single-source security_registry master table
-- (no `source` column — single external origin, normalized). Derived/
-- processed tables live in dwd, governance tables in govern.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - taxonomy_category / taxonomy_security_map  -> pg_default (NVMe, small metadata)
--   - industry_* / financial_* / corporate_action / bars_* / adjust_factor /
--     long_hu_bang / equity_structure -> warm_storage (SATA, business data)
--
-- JSONB advantages leveraged:
--   - GIN index on attrs_json / data_json for fast @>, ?, ?| queries
-- ============================================================

CREATE SCHEMA IF NOT EXISTS ods;

-- ──────────────────────────────────────────────────────────
-- 1. taxonomy_category
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.taxonomy_category (
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
CREATE INDEX IF NOT EXISTS idx_tc_parent ON ods.taxonomy_category (source, taxonomy, market, parent_code);
CREATE INDEX IF NOT EXISTS idx_tc_level ON ods.taxonomy_category (source, taxonomy, market, level);
CREATE INDEX IF NOT EXISTS idx_tc_index_code ON ods.taxonomy_category (source, taxonomy, index_code);
CREATE INDEX IF NOT EXISTS idx_tc_attrs_gin ON ods.taxonomy_category USING GIN (attrs_json);

-- ──────────────────────────────────────────────────────────
-- 2. taxonomy_security_map
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.taxonomy_security_map (
    source        VARCHAR(32) NOT NULL,
    taxonomy      VARCHAR(32) NOT NULL,
    category_code VARCHAR(64) NOT NULL,
    symbol        VARCHAR(32) NOT NULL,
    asset_type    VARCHAR(16) NOT NULL DEFAULT 'stock',
    market        VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    CONSTRAINT uk_src_tax_cat_sec UNIQUE (source, taxonomy, category_code, symbol, asset_type, market)
) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_tsm_symbol ON ods.taxonomy_security_map (symbol, asset_type, market);
CREATE INDEX IF NOT EXISTS idx_tsm_category ON ods.taxonomy_security_map (source, taxonomy, category_code);

-- ──────────────────────────────────────────────────────────
-- 3. industry_constituent
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.industry_constituent (
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
CREATE INDEX IF NOT EXISTS idx_ic_index_code ON ods.industry_constituent (source, taxonomy, index_code) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_ic_symbol ON ods.industry_constituent (symbol, market) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 4. industry_weight  (trade_date is DATE — folded from former 0003)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.industry_weight (
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    index_code   VARCHAR(64)    NOT NULL,
    con_code     VARCHAR(64)    NOT NULL DEFAULT '',
    symbol       VARCHAR(32)    NOT NULL,
    trade_date   DATE           NOT NULL,
    weight       NUMERIC(10,6),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, taxonomy, index_code, symbol, market, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_iw_index_date ON ods.industry_weight (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_iw_symbol_date ON ods.industry_weight (symbol, market, trade_date) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.industry_weight', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 5. industry_daily  (trade_date is DATE — folded from former 0003)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.industry_daily (
    source       VARCHAR(32)    NOT NULL,
    taxonomy     VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    index_code   VARCHAR(64)    NOT NULL,
    trade_date   DATE           NOT NULL,
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
    PRIMARY KEY (source, taxonomy, index_code, market, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_id_index_date ON ods.industry_daily (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_id_trade_date ON ods.industry_daily (source, taxonomy, trade_date) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.industry_daily', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 6. financial_statement
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.financial_statement (
    id               BIGSERIAL      PRIMARY KEY,
    source           VARCHAR(32)    NOT NULL,
    symbol           VARCHAR(32)    NOT NULL,
    market           VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    statement_type   VARCHAR(32)    NOT NULL,
    reporting_period VARCHAR(10)    NOT NULL,
    report_type      VARCHAR(32)    NOT NULL DEFAULT '',
    statement_code   VARCHAR(32)    NOT NULL DEFAULT '',
    security_name    VARCHAR(128)   NOT NULL DEFAULT '',
    ann_date         VARCHAR(10)    NOT NULL DEFAULT '',
    actual_ann_date  VARCHAR(10)    NOT NULL DEFAULT '',
    comp_type_code   SMALLINT       NOT NULL DEFAULT 0,
    data_json        JSONB          NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_fin_stmt UNIQUE (source, symbol, market, statement_type, reporting_period, report_type, statement_code),
    CONSTRAINT chk_financial_statement_data_json_object CHECK (jsonb_typeof(data_json) = 'object')
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_fs_symbol_type
    ON ods.financial_statement (symbol, statement_type) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_fs_report_period
    ON ods.financial_statement (reporting_period) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_fs_ann_date
    ON ods.financial_statement (ann_date) TABLESPACE warm_storage
    WHERE ann_date != '';
CREATE INDEX IF NOT EXISTS idx_fs_comp_type
    ON ods.financial_statement (comp_type_code) TABLESPACE warm_storage
    WHERE comp_type_code > 0;
CREATE INDEX IF NOT EXISTS idx_fs_data_gin
    ON ods.financial_statement USING GIN (data_json jsonb_path_ops) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 7. corporate_action
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.corporate_action (
    id               BIGSERIAL      PRIMARY KEY,
    source           VARCHAR(32)    NOT NULL,
    symbol           VARCHAR(32)    NOT NULL,
    market           VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    action_type      VARCHAR(32)    NOT NULL,
    report_period    VARCHAR(10)    NOT NULL DEFAULT '',
    ann_date         VARCHAR(10)    NOT NULL DEFAULT '',
    progress_code    VARCHAR(8)     NOT NULL DEFAULT '',
    data_json        JSONB          NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_corp_action UNIQUE (source, symbol, market, action_type, report_period, ann_date),
    CONSTRAINT chk_corporate_action_data_json_object CHECK (jsonb_typeof(data_json) = 'object')
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_ca_symbol_action
    ON ods.corporate_action (symbol, action_type) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_ca_report_period
    ON ods.corporate_action (report_period) TABLESPACE warm_storage
    WHERE report_period != '';
CREATE INDEX IF NOT EXISTS idx_ca_ann_date
    ON ods.corporate_action (ann_date) TABLESPACE warm_storage
    WHERE ann_date != '';
CREATE INDEX IF NOT EXISTS idx_ca_data_gin
    ON ods.corporate_action USING GIN (data_json jsonb_path_ops) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 8. bars_stock_zh_a_daily_nf  (A股日线不复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.bars_stock_zh_a_daily_nf (
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
    ON ods.bars_stock_zh_a_daily_nf (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bdnf_symbol
    ON ods.bars_stock_zh_a_daily_nf (symbol) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.bars_stock_zh_a_daily_nf', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 9. bars_stock_zh_a_daily_hfq  (A股日线前复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.bars_stock_zh_a_daily_hfq (
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
    ON ods.bars_stock_zh_a_daily_hfq (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bdhfq_symbol
    ON ods.bars_stock_zh_a_daily_hfq (symbol) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.bars_stock_zh_a_daily_hfq', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 10. bars_index_zh_a_daily_nf  (A股指数日线不复权)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.bars_index_zh_a_daily_nf (
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
    ON ods.bars_index_zh_a_daily_nf (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bidnf_symbol
    ON ods.bars_index_zh_a_daily_nf (symbol) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.bars_index_zh_a_daily_nf', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 11. bars_ext_baostock_stock_zh_a_daily
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.bars_ext_baostock_stock_zh_a_daily (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    turn        DECIMAL(10,4),
    pe_ttm      DECIMAL(20,4),
    ps_ttm      DECIMAL(20,4),
    pb_mrq      DECIMAL(20,4),
    pcf_ncf_ttm DECIMAL(20,4),
    CONSTRAINT uk_bars_ext_baostock PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_beb_trade_date
    ON ods.bars_ext_baostock_stock_zh_a_daily (trade_date) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_beb_symbol
    ON ods.bars_ext_baostock_stock_zh_a_daily (symbol) TABLESPACE warm_storage;

-- Convert to TimescaleDB hypertable (chunk by 1 year for daily data)
SELECT create_hypertable('ods.bars_ext_baostock_stock_zh_a_daily', 'trade_date',
                         if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '1 year');

-- ──────────────────────────────────────────────────────────
-- 12. adjust_factor
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.adjust_factor (
    id                  BIGSERIAL      PRIMARY KEY,
    source              VARCHAR(32)    NOT NULL,
    symbol              VARCHAR(32)    NOT NULL,
    market              VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    divid_operate_date  VARCHAR(10)    NOT NULL,
    fore_adjust_factor  NUMERIC(20,8),
    back_adjust_factor  NUMERIC(20,8),
    adjust_factor       NUMERIC(20,8),
    CONSTRAINT uk_adjust_factor UNIQUE (source, symbol, market, divid_operate_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_af_symbol_date
    ON ods.adjust_factor (symbol, market, divid_operate_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_af_operate_date
    ON ods.adjust_factor (divid_operate_date DESC) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 13. long_hu_bang
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.long_hu_bang (
    source            VARCHAR(32)    NOT NULL,
    symbol            VARCHAR(32)    NOT NULL,
    market            VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    trade_date        VARCHAR(10)    NOT NULL,
    security_name     VARCHAR(128)   NOT NULL DEFAULT '',
    reason_type       VARCHAR(32)    NOT NULL,
    reason_type_name  VARCHAR(256)   NOT NULL DEFAULT '',
    trader_name       VARCHAR(256)   NOT NULL,
    flow_mark         SMALLINT       NOT NULL,
    change_range      NUMERIC(20,6)  NOT NULL DEFAULT 0,
    buy_amount        NUMERIC(24,4)  NOT NULL DEFAULT 0,
    sell_amount       NUMERIC(24,4)  NOT NULL DEFAULT 0,
    total_amount      NUMERIC(24,4)  NOT NULL DEFAULT 0,
    total_volume      NUMERIC(24,4)  NOT NULL DEFAULT 0,
    CONSTRAINT uk_long_hu_bang UNIQUE (source, symbol, market, trade_date, reason_type, trader_name, flow_mark)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_lhb_symbol_date
    ON ods.long_hu_bang (symbol, market, trade_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_lhb_trade_date
    ON ods.long_hu_bang (trade_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_lhb_reason_date
    ON ods.long_hu_bang (reason_type, trade_date DESC, flow_mark) TABLESPACE warm_storage;

-- ──────────────────────────────────────────────────────────
-- 14. equity_structure
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.equity_structure (
    id              BIGSERIAL      PRIMARY KEY,
    source          VARCHAR(32)    NOT NULL,
    symbol          VARCHAR(32)    NOT NULL,
    market          VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    ann_date        VARCHAR(10)    NOT NULL DEFAULT '',
    change_date     VARCHAR(10)    NOT NULL,
    current_sign    SMALLINT       NOT NULL DEFAULT 0,
    is_valid        SMALLINT       NOT NULL DEFAULT 1,
    data_json       JSONB          NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_equity_structure UNIQUE (source, symbol, market, change_date, ann_date),
    CONSTRAINT chk_equity_structure_data_json_object CHECK (jsonb_typeof(data_json) = 'object')
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_es_symbol_date
    ON ods.equity_structure (symbol, market, change_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_es_change_date
    ON ods.equity_structure (change_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_es_current_valid
    ON ods.equity_structure (source, market, current_sign, is_valid)
    TABLESPACE warm_storage
    WHERE current_sign = 1 AND is_valid = 1;
CREATE INDEX IF NOT EXISTS idx_es_data_gin
    ON ods.equity_structure USING GIN (data_json jsonb_path_ops) TABLESPACE warm_storage;

COMMENT ON TABLE ods.equity_structure IS 'AmazingData get_equity_structure 股本结构数据。用于估值、市值、流通股本、限售股和因子计算。';
COMMENT ON COLUMN ods.equity_structure.id IS '自增主键。';
COMMENT ON COLUMN ods.equity_structure.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.equity_structure.symbol IS '证券代码，内部统一使用纯代码，不含交易所后缀。';
COMMENT ON COLUMN ods.equity_structure.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.equity_structure.ann_date IS '公告日期，统一 YYYY-MM-DD 格式；来自 SDK ANN_DATE。';
COMMENT ON COLUMN ods.equity_structure.change_date IS '股本变动日期，统一 YYYY-MM-DD 格式；来自 SDK CHANGE_DATE，是该表主要时间轴。';
COMMENT ON COLUMN ods.equity_structure.current_sign IS '最新标志；来自 SDK CURRENT_SIGN，1 表示最新，0 表示非最新。';
COMMENT ON COLUMN ods.equity_structure.is_valid IS '有效标志；来自 SDK IS_VALID，1 表示有效，0 表示无效。';
COMMENT ON COLUMN ods.equity_structure.data_json IS 'AmazingData 股本结构明细 JSONB object。字段契约见 govern.data_field_dictionary dataset=equity_structure。';
COMMENT ON COLUMN ods.equity_structure.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.equity_structure.updated_at IS '记录更新时间。';

-- ──────────────────────────────────────────────────────────
-- 15. security_registry  (unified security identifier master)
--    Single external origin: artemis StockZHAList task downloads from
--    AmazingData get_code_info and POSTs to /api/v2/securities/upsert.
--    No `source` column — single source, normalized master data.
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.security_registry (
    symbol       VARCHAR(32)    NOT NULL,
    asset_type   VARCHAR(16)    NOT NULL,
    market       VARCHAR(16)    NOT NULL,
    exchange     VARCHAR(8)     NOT NULL,
    name         VARCHAR(128)   NOT NULL DEFAULT '',
    full_name    VARCHAR(256),
    status       VARCHAR(16)    NOT NULL DEFAULT 'active',
    list_date    DATE,
    delist_date  DATE,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_security_registry PRIMARY KEY (symbol, asset_type, market)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_sr_asset_market
    ON ods.security_registry (asset_type, market);
CREATE INDEX IF NOT EXISTS idx_sr_exchange
    ON ods.security_registry (exchange);
CREATE INDEX IF NOT EXISTS idx_sr_status
    ON ods.security_registry (status)
    WHERE status != 'active';

COMMENT ON TABLE ods.security_registry IS '统一证券注册表（股票/ETF/指数基础信息）。单一外部来源：artemis 从 AmazingData get_code_info 下载，POST /api/v2/securities/upsert 落地。单源主数据，无 source 列。';
