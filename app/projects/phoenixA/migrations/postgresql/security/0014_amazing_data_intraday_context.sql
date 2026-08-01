-- AmazingData intraday context for the T-trading signal workbench.
-- Artemis converts AmazingData's forward/start label to the first instant at
-- which the complete bar is available before writing trade_date.

CREATE TABLE IF NOT EXISTS ods.bars_stock_zh_a_min1_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_stock_zh_a_min1_nf PRIMARY KEY (security_id, trade_date),
    CONSTRAINT ck_bars_stock_zh_a_min1_nf_ohlc CHECK (
        low <= high AND open BETWEEN low AND high AND close BETWEEN low AND high
    ),
    CONSTRAINT ck_bars_stock_zh_a_min1_nf_volume CHECK (volume IS NULL OR volume >= 0),
    CONSTRAINT ck_bars_stock_zh_a_min1_nf_amount CHECK (amount IS NULL OR amount >= 0)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_stock_zh_a_min1_nf_security_time
    ON ods.bars_stock_zh_a_min1_nf (security_id, trade_date DESC)
    TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_stock_zh_a_min1_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 month'
);

CREATE TABLE IF NOT EXISTS ods.bars_stock_zh_a_min30_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_stock_zh_a_min30_nf PRIMARY KEY (security_id, trade_date),
    CONSTRAINT ck_bars_stock_zh_a_min30_nf_ohlc CHECK (
        low <= high AND open BETWEEN low AND high AND close BETWEEN low AND high
    ),
    CONSTRAINT ck_bars_stock_zh_a_min30_nf_volume CHECK (volume IS NULL OR volume >= 0),
    CONSTRAINT ck_bars_stock_zh_a_min30_nf_amount CHECK (amount IS NULL OR amount >= 0)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_stock_zh_a_min30_nf_security_time
    ON ods.bars_stock_zh_a_min30_nf (security_id, trade_date DESC)
    TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_stock_zh_a_min30_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '3 months'
);

CREATE TABLE IF NOT EXISTS ods.bars_index_zh_a_min1_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_index_zh_a_min1_nf PRIMARY KEY (security_id, trade_date),
    CONSTRAINT ck_bars_index_zh_a_min1_nf_ohlc CHECK (
        low <= high AND open BETWEEN low AND high AND close BETWEEN low AND high
    ),
    CONSTRAINT ck_bars_index_zh_a_min1_nf_volume CHECK (volume IS NULL OR volume >= 0),
    CONSTRAINT ck_bars_index_zh_a_min1_nf_amount CHECK (amount IS NULL OR amount >= 0)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_index_zh_a_min1_nf_security_time
    ON ods.bars_index_zh_a_min1_nf (security_id, trade_date DESC)
    TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_index_zh_a_min1_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 month'
);

CREATE TABLE IF NOT EXISTS ods.bars_index_zh_a_min5_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_index_zh_a_min5_nf PRIMARY KEY (security_id, trade_date),
    CONSTRAINT ck_bars_index_zh_a_min5_nf_ohlc CHECK (
        low <= high AND open BETWEEN low AND high AND close BETWEEN low AND high
    ),
    CONSTRAINT ck_bars_index_zh_a_min5_nf_volume CHECK (volume IS NULL OR volume >= 0),
    CONSTRAINT ck_bars_index_zh_a_min5_nf_amount CHECK (amount IS NULL OR amount >= 0)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_index_zh_a_min5_nf_security_time
    ON ods.bars_index_zh_a_min5_nf (security_id, trade_date DESC)
    TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_index_zh_a_min5_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 month'
);

COMMENT ON COLUMN ods.bars_stock_zh_a_min1_nf.trade_date IS
    'Complete-bar availability time. AmazingData 09:30 min1 is stored as 09:31 Asia/Shanghai.';
COMMENT ON COLUMN ods.bars_stock_zh_a_min30_nf.trade_date IS
    'Complete-bar availability time converted from AmazingData forward/start labels.';
COMMENT ON COLUMN ods.bars_index_zh_a_min1_nf.trade_date IS
    'Complete-bar availability time converted from AmazingData forward/start labels.';
COMMENT ON COLUMN ods.bars_index_zh_a_min5_nf.trade_date IS
    'Complete-bar availability time converted from AmazingData forward/start labels.';
