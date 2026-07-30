-- A-share intraday bars used by the Artemis T-trading research workbench.
-- Raw, non-adjusted prices are the canonical execution/replay input.

CREATE TABLE IF NOT EXISTS ods.bars_stock_zh_a_min5_nf (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  TIMESTAMPTZ    NOT NULL,
    open        DECIMAL(20,4)  NOT NULL,
    high        DECIMAL(20,4)  NOT NULL,
    low         DECIMAL(20,4)  NOT NULL,
    close       DECIMAL(20,4)  NOT NULL,
    volume      BIGINT,
    amount      BIGINT,
    preclose    DECIMAL(20,4),
    pct_chg     DECIMAL(10,4),
    CONSTRAINT uk_bars_stock_zh_a_min5_nf PRIMARY KEY (symbol, trade_date),
    CONSTRAINT ck_bars_stock_zh_a_min5_nf_ohlc CHECK (
        low <= high
        AND open BETWEEN low AND high
        AND close BETWEEN low AND high
    ),
    CONSTRAINT ck_bars_stock_zh_a_min5_nf_volume CHECK (volume IS NULL OR volume >= 0),
    CONSTRAINT ck_bars_stock_zh_a_min5_nf_amount CHECK (amount IS NULL OR amount >= 0)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_stock_zh_a_min5_nf_symbol_time
    ON ods.bars_stock_zh_a_min5_nf (symbol, trade_date DESC)
    TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_bars_stock_zh_a_min5_nf_time
    ON ods.bars_stock_zh_a_min5_nf (trade_date DESC)
    TABLESPACE warm_storage;

SELECT create_hypertable(
    'ods.bars_stock_zh_a_min5_nf',
    'trade_date',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 month'
);

COMMENT ON TABLE ods.bars_stock_zh_a_min5_nf IS
    'A-share 5-minute raw bars for causal replay. trade_date is the complete exchange bar timestamp, not a date-only value.';
COMMENT ON COLUMN ods.bars_stock_zh_a_min5_nf.trade_date IS
    'RFC3339-compatible exchange bar timestamp stored as TIMESTAMPTZ; Artemis must not truncate it to YYYY-MM-DD.';
