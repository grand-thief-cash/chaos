-- ============================================================
-- PhoenixA PostgreSQL Migration 0014: Equity Structure
-- Target: chaos_db, schema: security_dev / security
-- Scope: equity_structure
-- Storage tier: warm_storage
-- Reason: AmazingData get_equity_structure business dataset used by
--         valuation, market-cap, float-share and factor calculations.
-- ============================================================

DROP TABLE IF EXISTS equity_structure CASCADE;

CREATE TABLE equity_structure (
    id              BIGSERIAL      PRIMARY KEY,
    source          VARCHAR(32)    NOT NULL,
    symbol          VARCHAR(32)    NOT NULL,              -- 纯代码，如 "000001"（不含交易所后缀）
    market          VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    ann_date        VARCHAR(10)    NOT NULL DEFAULT '',   -- YYYY-MM-DD 格式
    change_date     VARCHAR(10)    NOT NULL,              -- YYYY-MM-DD 格式
    current_sign    SMALLINT       NOT NULL DEFAULT 0,    -- 1:最新 0:非最新
    is_valid        SMALLINT       NOT NULL DEFAULT 1,    -- 1:有效 0:无效
    data_json       JSONB          NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_equity_structure UNIQUE (source, symbol, market, change_date, ann_date),
    CONSTRAINT chk_equity_structure_data_json_object CHECK (jsonb_typeof(data_json) = 'object')
) TABLESPACE warm_storage;

CREATE INDEX idx_es_symbol_date
    ON equity_structure (symbol, market, change_date DESC) TABLESPACE warm_storage;

CREATE INDEX idx_es_change_date
    ON equity_structure (change_date DESC) TABLESPACE warm_storage;

CREATE INDEX idx_es_current_valid
    ON equity_structure (source, market, current_sign, is_valid)
    TABLESPACE warm_storage
    WHERE current_sign = 1 AND is_valid = 1;

CREATE INDEX idx_es_data_gin
    ON equity_structure USING GIN (data_json jsonb_path_ops) TABLESPACE warm_storage;

COMMENT ON TABLE equity_structure IS 'AmazingData get_equity_structure 股本结构数据。用于估值、市值、流通股本、限售股和因子计算。';
COMMENT ON COLUMN equity_structure.id IS '自增主键。';
COMMENT ON COLUMN equity_structure.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN equity_structure.symbol IS '证券代码，内部统一使用纯代码，不含交易所后缀。';
COMMENT ON COLUMN equity_structure.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN equity_structure.ann_date IS '公告日期，统一 YYYY-MM-DD 格式；来自 SDK ANN_DATE。';
COMMENT ON COLUMN equity_structure.change_date IS '股本变动日期，统一 YYYY-MM-DD 格式；来自 SDK CHANGE_DATE，是该表主要时间轴。';
COMMENT ON COLUMN equity_structure.current_sign IS '最新标志；来自 SDK CURRENT_SIGN，1 表示最新，0 表示非最新。';
COMMENT ON COLUMN equity_structure.is_valid IS '有效标志；来自 SDK IS_VALID，1 表示有效，0 表示无效。';
COMMENT ON COLUMN equity_structure.data_json IS 'AmazingData 股本结构明细 JSONB object。字段契约见 data_field_dictionary dataset=equity_structure。';
COMMENT ON COLUMN equity_structure.created_at IS '记录创建时间。';
COMMENT ON COLUMN equity_structure.updated_at IS '记录更新时间。';
