-- ============================================================
-- PhoenixA PostgreSQL Migration 0010: Adjust Factor
-- Target: chaos_db, schema: security_dev / security
-- Scope: adjust_factor
-- Storage tier: warm_storage
-- Reason: market-wide symbol × ex-dividend-date rows for adjusted price reconstruction
-- ============================================================

CREATE TABLE IF NOT EXISTS adjust_factor (
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
    ON adjust_factor (symbol, market, divid_operate_date DESC) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_af_operate_date
    ON adjust_factor (divid_operate_date DESC) TABLESPACE warm_storage;


