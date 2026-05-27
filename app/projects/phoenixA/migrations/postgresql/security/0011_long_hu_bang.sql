-- ============================================================
-- PhoenixA PostgreSQL Migration 0011: Long Hu Bang
-- Target: chaos_db, schema: security_dev / security
-- Scope: long_hu_bang
-- Storage tier: warm_storage
-- Reason: A-share event-detail dataset with a small, stable flat schema
-- ============================================================

CREATE TABLE IF NOT EXISTS long_hu_bang (
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
    ON long_hu_bang (symbol, market, trade_date DESC) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_lhb_trade_date
    ON long_hu_bang (trade_date DESC) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_lhb_reason_date
    ON long_hu_bang (reason_type, trade_date DESC, flow_mark) TABLESPACE warm_storage;


