-- ODS market-data foundation.
--
-- This file contains final CREATE definitions only. Corrections to tables
-- owned by 0001 are folded into 0001 instead of patched here.

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
    'AmazingData 沪深融资融券市场汇总，按交易日一行；不是单一证券事实。';

-- symbol is a capital-flow channel code, not a security identifier.
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
    '沪深港通通道级日频资金流。symbol 表示北向/南向/通道，不是证券代码。';

-- symbol is a QVIX series code (50ETF/300INDEX...), not a security identity.
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
    'AKShare QVIX 指标序列；symbol 是指标序列代码，不是证券主数据。';

CREATE TABLE IF NOT EXISTS ods.option_daily_stats (
    exchange                       VARCHAR(8) NOT NULL,
    underlying_security_id         BIGINT NOT NULL REFERENCES ods.security_registry(id),
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
        PRIMARY KEY (exchange, underlying_security_id, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_option_daily_stats_date
    ON ods.option_daily_stats (trade_date DESC) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.option_daily_stats', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
COMMENT ON TABLE ods.option_daily_stats IS
    '上交所、深交所股票期权每日统计；标的统一引用 security_registry。';

CREATE TABLE IF NOT EXISTS ods.market_observation_daily (
    security_id      BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date       DATE NOT NULL,
    observation_type VARCHAR(32) NOT NULL,
    source           VARCHAR(32) NOT NULL,
    value            NUMERIC(30,10) NOT NULL,
    unit             VARCHAR(32) NOT NULL,
    extra_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uk_market_observation_daily
        PRIMARY KEY (security_id, trade_date, observation_type, source),
    CONSTRAINT ck_market_observation_extra
        CHECK (jsonb_typeof(extra_json) = 'object')
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
    '纵向市场观测事实表；security_id 外键引用 security_registry。';

CREATE TABLE IF NOT EXISTS ods.security_event (
    id          BIGSERIAL PRIMARY KEY,
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    source      VARCHAR(32) NOT NULL,
    event_type  VARCHAR(32) NOT NULL,
    event_date  DATE NOT NULL,
    title       VARCHAR(512) NOT NULL,
    url         TEXT,
    data_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uk_security_event
        UNIQUE (security_id, source, event_type, event_date, title),
    CONSTRAINT ck_security_event_data
        CHECK (jsonb_typeof(data_json) = 'object')
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_se_security_date
    ON ods.security_event (security_id, event_date DESC) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_se_type_date
    ON ods.security_event (event_type, event_date DESC) TABLESPACE warm_storage;
COMMENT ON TABLE ods.security_event IS
    'Point-in-time security announcements and disclosure schedules.';

CREATE TABLE IF NOT EXISTS ods.bars_index_global_daily_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_index_global_daily_nf
        PRIMARY KEY (security_id, trade_date)
) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_bigdnf_trade_date
    ON ods.bars_index_global_daily_nf (trade_date) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_index_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_fx_global_daily_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_fx_global_daily_nf
        PRIMARY KEY (security_id, trade_date)
) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_fx_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_futures_global_daily_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_futures_global_daily_nf
        PRIMARY KEY (security_id, trade_date)
) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_futures_global_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_stock_us_daily_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_stock_us_daily_nf
        PRIMARY KEY (security_id, trade_date)
) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_stock_us_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);

CREATE TABLE IF NOT EXISTS ods.bars_stock_hk_daily_nf (
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    trade_date DATE NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT,
    amount BIGINT,
    preclose DECIMAL(20,4),
    pct_chg DECIMAL(10,4),
    CONSTRAINT uk_bars_stock_hk_daily_nf
        PRIMARY KEY (security_id, trade_date)
) TABLESPACE warm_storage;
SELECT create_hypertable(
    'ods.bars_stock_hk_daily_nf', 'trade_date',
    if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 year'
);
