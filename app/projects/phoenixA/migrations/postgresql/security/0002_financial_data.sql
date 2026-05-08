-- ============================================================
-- PhoenixA PostgreSQL Migration 0002: Financial Data Tables
-- Target: chaos_db, schema: security_dev
-- Scope: financial_statement, corporate_action
--
-- Migrated from MySQL JSON → PostgreSQL JSONB to leverage:
--   - GIN index on data_json for fast @>, ?, ?| queries
--   - Native jsonb operators (->, ->>, @>) for ad-hoc filtering
--   - jsonb_object_keys() for schema discovery (replacing JSON_TABLE)
--   - Partial indexes for common query patterns
-- ============================================================

-- 1. financial_statement
CREATE TABLE IF NOT EXISTS financial_statement (
    id               BIGSERIAL      PRIMARY KEY,
    source           VARCHAR(32)    NOT NULL,
    symbol           VARCHAR(32)    NOT NULL,
    market           VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    statement_type   VARCHAR(32)    NOT NULL,       -- balance_sheet / income / cashflow / profit_express / profit_notice
    reporting_period VARCHAR(10)    NOT NULL,        -- YYYYMMDD
    report_type      VARCHAR(32)    NOT NULL DEFAULT '',  -- 报告期名称
    statement_code   VARCHAR(32)    NOT NULL DEFAULT '',  -- 报表类型代码
    security_name    VARCHAR(128)   NOT NULL DEFAULT '',
    ann_date         VARCHAR(10)    NOT NULL DEFAULT '',
    actual_ann_date  VARCHAR(10)    NOT NULL DEFAULT '',
    comp_type_code   SMALLINT       NOT NULL DEFAULT 0,   -- 1:非金融 2:银行 3:保险 4:证券
    data_json        JSONB          NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_fin_stmt UNIQUE (source, symbol, market, statement_type, reporting_period, report_type, statement_code)
);

-- B-tree indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_fs_symbol_type
    ON financial_statement (symbol, statement_type);
CREATE INDEX IF NOT EXISTS idx_fs_report_period
    ON financial_statement (reporting_period);
CREATE INDEX IF NOT EXISTS idx_fs_ann_date
    ON financial_statement (ann_date)
    WHERE ann_date != '';
CREATE INDEX IF NOT EXISTS idx_fs_comp_type
    ON financial_statement (comp_type_code)
    WHERE comp_type_code > 0;

-- GIN index on JSONB: enables fast @>, ?, ?| queries on data_json
-- e.g. WHERE data_json @> '{"TOTAL_ASSETS": 1000000}'
-- e.g. WHERE data_json ? 'TOTAL_ASSETS'
-- e.g. WHERE data_json ->> 'TOTAL_ASSETS' IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_fs_data_gin
    ON financial_statement USING GIN (data_json jsonb_path_ops);

-- 2. corporate_action
CREATE TABLE IF NOT EXISTS corporate_action (
    id               BIGSERIAL      PRIMARY KEY,
    source           VARCHAR(32)    NOT NULL,
    symbol           VARCHAR(32)    NOT NULL,
    market           VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    action_type      VARCHAR(32)    NOT NULL,       -- dividend / right_issue
    report_period    VARCHAR(10)    NOT NULL DEFAULT '',   -- 分红/配股年度
    ann_date         VARCHAR(10)    NOT NULL DEFAULT '',
    progress_code    VARCHAR(8)     NOT NULL DEFAULT '',
    data_json        JSONB          NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_corp_action UNIQUE (source, symbol, market, action_type, report_period, ann_date)
);

-- B-tree indexes
CREATE INDEX IF NOT EXISTS idx_ca_symbol_action
    ON corporate_action (symbol, action_type);
CREATE INDEX IF NOT EXISTS idx_ca_report_period
    ON corporate_action (report_period)
    WHERE report_period != '';
CREATE INDEX IF NOT EXISTS idx_ca_ann_date
    ON corporate_action (ann_date)
    WHERE ann_date != '';

-- GIN index on JSONB
CREATE INDEX IF NOT EXISTS idx_ca_data_gin
    ON corporate_action USING GIN (data_json jsonb_path_ops);

