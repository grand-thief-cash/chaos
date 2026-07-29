-- Phase 0 ODS market-data foundation.
-- Preserve source nulls and add the two BaoStock daily status observations.

ALTER TABLE ods.bars_ext_baostock_stock_zh_a_daily
    ADD COLUMN IF NOT EXISTS trade_status SMALLINT,
    ADD COLUMN IF NOT EXISTS is_st BOOLEAN;

COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.trade_status
    IS 'BaoStock tradestatus: 1=normal trading, 0=suspended; NULL=source unavailable.';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.is_st
    IS 'BaoStock isST: true=ST security, false=non-ST; NULL=source unavailable.';

ALTER TABLE ods.long_hu_bang
    ALTER COLUMN change_range DROP NOT NULL,
    ALTER COLUMN change_range DROP DEFAULT,
    ALTER COLUMN buy_amount DROP NOT NULL,
    ALTER COLUMN buy_amount DROP DEFAULT,
    ALTER COLUMN sell_amount DROP NOT NULL,
    ALTER COLUMN sell_amount DROP DEFAULT,
    ALTER COLUMN total_amount DROP NOT NULL,
    ALTER COLUMN total_amount DROP DEFAULT,
    ALTER COLUMN total_volume DROP NOT NULL,
    ALTER COLUMN total_volume DROP DEFAULT;

CREATE TABLE IF NOT EXISTS ods.margin_summary_daily (
    trade_date               DATE NOT NULL PRIMARY KEY,
    financing_balance        NUMERIC(30,4),
    financing_buy            NUMERIC(30,4),
    financing_repay          NUMERIC(30,4),
    securities_balance       NUMERIC(30,4),
    securities_sell_volume   NUMERIC(30,4),
    margin_total_balance      NUMERIC(30,4)
) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.margin_summary_daily', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.margin_summary_daily IS
    'AmazingData 沪深融资融券市场汇总，按交易日一行。';
COMMENT ON COLUMN ods.margin_summary_daily.financing_balance IS
    '融资余额，人民币元。';
COMMENT ON COLUMN ods.margin_summary_daily.securities_sell_volume IS
    '融券卖出量，股。';

CREATE TABLE IF NOT EXISTS ods.hsgt_daily (
    symbol                    VARCHAR(16) NOT NULL,
    trade_date                DATE NOT NULL,
    net_buy                   NUMERIC(30,4),
    buy_amount                NUMERIC(30,4),
    sell_amount               NUMERIC(30,4),
    cumulative_net_buy        NUMERIC(30,4),
    capital_inflow            NUMERIC(30,4),
    quota_balance             NUMERIC(30,4),
    holding_market_value      NUMERIC(30,4),
    leading_stock_name        VARCHAR(64),
    leading_stock_symbol      VARCHAR(32),
    leading_stock_pct_chg     NUMERIC(20,6),
    benchmark_value           NUMERIC(20,6),
    benchmark_pct_chg         NUMERIC(20,6),
    CONSTRAINT uk_hsgt_daily PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_hsgt_daily_date
    ON ods.hsgt_daily (trade_date DESC) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.hsgt_daily', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.hsgt_daily IS
    'AKShare stock_hsgt_hist_em 日频数据；symbol 区分北向、南向及各通道。';
COMMENT ON COLUMN ods.hsgt_daily.net_buy IS
    '当日成交净买额；币种与单位遵循对应 symbol 的来源定义。';

CREATE TABLE IF NOT EXISTS ods.option_qvix_daily (
    symbol       VARCHAR(16) NOT NULL,
    trade_date   DATE NOT NULL,
    open         NUMERIC(20,6) NOT NULL,
    high         NUMERIC(20,6) NOT NULL,
    low          NUMERIC(20,6) NOT NULL,
    close        NUMERIC(20,6) NOT NULL,
    CONSTRAINT uk_option_qvix_daily PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_option_qvix_daily_date
    ON ods.option_qvix_daily (trade_date DESC) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.option_qvix_daily', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.option_qvix_daily IS
    'AKShare 各标的期权 QVIX 日线；symbol 区分 50ETF、300ETF 等类型。';

CREATE TABLE IF NOT EXISTS ods.option_daily_stats (
    exchange                       VARCHAR(8) NOT NULL,
    underlying_symbol              VARCHAR(16) NOT NULL,
    trade_date                     DATE NOT NULL,
    underlying_name                VARCHAR(64) NOT NULL DEFAULT '',
    contract_count                 BIGINT,
    turnover                       BIGINT,
    volume                         BIGINT,
    call_volume                    BIGINT,
    put_volume                     BIGINT,
    put_call_volume_ratio          NUMERIC(20,6),
    open_interest                  BIGINT,
    call_open_interest             BIGINT,
    put_open_interest              BIGINT,
    put_call_open_interest_ratio   NUMERIC(20,6),
    CONSTRAINT uk_option_daily_stats
        PRIMARY KEY (exchange, underlying_symbol, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_option_daily_stats_date
    ON ods.option_daily_stats (trade_date DESC) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.option_daily_stats', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.option_daily_stats IS
    '上交所、深交所股票期权每日统计；exchange 和 underlying_symbol 区分数据。';
COMMENT ON COLUMN ods.option_daily_stats.turnover IS
    '上交所总成交额，万元；深交所来源无该字段时为 NULL。';
COMMENT ON COLUMN ods.option_daily_stats.put_call_volume_ratio IS
    '上交所来源认沽/认购成交比原值。';
COMMENT ON COLUMN ods.option_daily_stats.put_call_open_interest_ratio IS
    '深交所来源认沽/认购持仓比原值。';

-- Development replacement of the first wide-table draft. Tradable global
-- futures/FX/indexes use standard Bars; scalar macro/rate series use this
-- extensible vertical table.
DROP TABLE IF EXISTS ods.global_rate_daily;
DROP TABLE IF EXISTS ods.global_fx_daily;
DROP TABLE IF EXISTS ods.global_commodity_daily;

CREATE TABLE IF NOT EXISTS ods.market_observation_daily (
    security_id      BIGINT NOT NULL,
    trade_date       DATE NOT NULL,
    observation_type VARCHAR(32) NOT NULL,
    source           VARCHAR(32) NOT NULL,
    value            NUMERIC(30,10) NOT NULL,
    unit             VARCHAR(32) NOT NULL,
    extra_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uk_market_observation_daily
        PRIMARY KEY (security_id, trade_date, observation_type, source)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_mod_trade_date
    ON ods.market_observation_daily (trade_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_mod_type_date
    ON ods.market_observation_daily (observation_type, trade_date DESC)
    TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.market_observation_daily', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.market_observation_daily IS
    '纵向市场观测事实表；security_id 逻辑关联 security_registry，适用于收益率、利差、GDP等非OHLC标量序列。';
COMMENT ON COLUMN ods.market_observation_daily.observation_type IS
    '序列分类，如 bond_yield、yield_spread、gdp_yoy；新增类型不需要增加列。';

CREATE TABLE IF NOT EXISTS ods.security_event (
    id          BIGSERIAL PRIMARY KEY,
    security_id BIGINT NOT NULL,
    source      VARCHAR(32) NOT NULL,
    event_type  VARCHAR(32) NOT NULL,
    event_date  DATE NOT NULL,
    title       VARCHAR(512) NOT NULL,
    url         TEXT,
    data_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uk_security_event
        UNIQUE (security_id, source, event_type, event_date, title)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_se_security_date
    ON ods.security_event (security_id, event_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_se_type_date
    ON ods.security_event (event_type, event_date DESC) TABLESPACE warm_storage;
COMMENT ON TABLE ods.security_event IS
    'Minimal point-in-time security announcements and disclosure schedules.';

CREATE TABLE IF NOT EXISTS ods.bars_index_global_daily_nf (
    symbol VARCHAR(32) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_index_global_daily_nf PRIMARY KEY (symbol, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bigdnf_trade_date
    ON ods.bars_index_global_daily_nf (trade_date) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_index_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_fx_global_daily_nf (
    LIKE ods.bars_index_global_daily_nf INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) TABLESPACE warm_storage;
ALTER TABLE ods.bars_fx_global_daily_nf
    DROP CONSTRAINT IF EXISTS uk_bars_index_global_daily_nf;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'ods.bars_fx_global_daily_nf'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE ods.bars_fx_global_daily_nf
            ADD CONSTRAINT uk_bars_fx_global_daily_nf
            PRIMARY KEY (symbol, trade_date);
    END IF;
END
$$;
SELECT create_hypertable(
    'ods.bars_fx_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_futures_global_daily_nf (
    LIKE ods.bars_index_global_daily_nf INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) TABLESPACE warm_storage;
ALTER TABLE ods.bars_futures_global_daily_nf
    DROP CONSTRAINT IF EXISTS uk_bars_index_global_daily_nf;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'ods.bars_futures_global_daily_nf'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE ods.bars_futures_global_daily_nf
            ADD CONSTRAINT uk_bars_futures_global_daily_nf
            PRIMARY KEY (symbol, trade_date);
    END IF;
END
$$;
SELECT create_hypertable(
    'ods.bars_futures_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_stock_us_daily_nf (
    LIKE ods.bars_index_global_daily_nf INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) TABLESPACE warm_storage;
ALTER TABLE ods.bars_stock_us_daily_nf
    DROP CONSTRAINT IF EXISTS uk_bars_index_global_daily_nf;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'ods.bars_stock_us_daily_nf'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE ods.bars_stock_us_daily_nf
            ADD CONSTRAINT uk_bars_stock_us_daily_nf PRIMARY KEY (symbol, trade_date);
    END IF;
END
$$;
SELECT create_hypertable(
    'ods.bars_stock_us_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_stock_hk_daily_nf (
    LIKE ods.bars_index_global_daily_nf INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) TABLESPACE warm_storage;
ALTER TABLE ods.bars_stock_hk_daily_nf
    DROP CONSTRAINT IF EXISTS uk_bars_index_global_daily_nf;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'ods.bars_stock_hk_daily_nf'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE ods.bars_stock_hk_daily_nf
            ADD CONSTRAINT uk_bars_stock_hk_daily_nf PRIMARY KEY (symbol, trade_date);
    END IF;
END
$$;
SELECT create_hypertable(
    'ods.bars_stock_hk_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
