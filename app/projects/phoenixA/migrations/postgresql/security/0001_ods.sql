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

COMMENT ON TABLE ods.taxonomy_category IS '行业分类节点（树形结构）。ODS 源数据落地表，由 artemis 从 AmazingData get_industry_base_info（SWHY 申万，指南 3.5.13.1）及麦蕊 API（MAIRUI）下载后 POST 落地。';
COMMENT ON COLUMN ods.taxonomy_category.id IS '自增主键。';
COMMENT ON COLUMN ods.taxonomy_category.source IS '数据源标识，如 amazing_data / mairui。';
COMMENT ON COLUMN ods.taxonomy_category.taxonomy IS '分类体系标识，如 swhy（申万宏源）/ mairui（麦蕊）。';
COMMENT ON COLUMN ods.taxonomy_category.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.taxonomy_category.code IS '行业分类节点代码；SWHY 来自 SDK INDUSTRY_CODE。';
COMMENT ON COLUMN ods.taxonomy_category.name IS '行业名称；SWHY 按 LEVEL_TYPE 取 LEVEL1_NAME/LEVEL2_NAME/LEVEL3_NAME 之一。';
COMMENT ON COLUMN ods.taxonomy_category.parent_code IS '父级行业节点代码；SWHY 由名称层级匹配派生，MAIRUI 来自 pcode。';
COMMENT ON COLUMN ods.taxonomy_category.index_code IS '行业指数代码；SWHY 来自 SDK INDEX_CODE。';
COMMENT ON COLUMN ods.taxonomy_category.level IS '行业层级；SWHY 来自 SDK LEVEL_TYPE（1=一级行业，2=二级行业，3=三级行业）。';
COMMENT ON COLUMN ods.taxonomy_category.is_leaf IS '是否叶子节点；SWHY = (level==3)，MAIRUI = (isleaf==1)。';
COMMENT ON COLUMN ods.taxonomy_category.attrs_json IS '附加属性 JSONB；SWHY 含 IS_PUB（是否发布，1已发布/2未发布）、CHANGE_REASON（变动原因）。';
COMMENT ON COLUMN ods.taxonomy_category.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.taxonomy_category.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.taxonomy_security_map IS '证券↔行业分类节点映射表。非下载任务直接写入，由 PhoenixA 从 industry_constituent × taxonomy_category JOIN 派生（taxonomy_dao.go SyncMappingsFromConstituents）。';
COMMENT ON COLUMN ods.taxonomy_security_map.source IS '数据源标识，沿用成分股表 source（如 amazing_data）。';
COMMENT ON COLUMN ods.taxonomy_security_map.taxonomy IS '分类体系标识，沿用成分股表 taxonomy（如 swhy）。';
COMMENT ON COLUMN ods.taxonomy_security_map.category_code IS '行业分类节点代码，等于 taxonomy_category.code（= SDK INDUSTRY_CODE）。';
COMMENT ON COLUMN ods.taxonomy_security_map.symbol IS '证券代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.taxonomy_security_map.asset_type IS '资产类型，派生时固定为 stock。';
COMMENT ON COLUMN ods.taxonomy_security_map.market IS '市场标识，沿用成分股表 market（如 zh_a）。';

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

COMMENT ON TABLE ods.industry_constituent IS '行业指数成分股。ODS 落地表，由 artemis 从 AmazingData get_industry_constituent（SWHY 申万，指南 3.5.13.2）下载后 POST 落地。';
COMMENT ON COLUMN ods.industry_constituent.id IS '自增主键。';
COMMENT ON COLUMN ods.industry_constituent.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.industry_constituent.taxonomy IS '分类体系标识，如 swhy（申万宏源）。';
COMMENT ON COLUMN ods.industry_constituent.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.industry_constituent.index_code IS '行业指数代码；SDK INDEX_CODE。';
COMMENT ON COLUMN ods.industry_constituent.con_code IS '成分股代码（含交易所后缀，如 688526.SH）；SDK CON_CODE。';
COMMENT ON COLUMN ods.industry_constituent.symbol IS '证券代码（纯代码，con_code 去交易所后缀）。';
COMMENT ON COLUMN ods.industry_constituent.index_name IS '指数名称；SDK INDEX_NAME。';
COMMENT ON COLUMN ods.industry_constituent.in_date IS '纳入日期；SDK INDATE。';
COMMENT ON COLUMN ods.industry_constituent.out_date IS '剔除日期；SDK OUTDATE，未剔除时为空。';
COMMENT ON COLUMN ods.industry_constituent.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.industry_constituent.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.industry_weight IS '行业指数成分股日权重。ODS 落地表，由 artemis 从 AmazingData get_industry_weight（SWHY 申万，指南 3.5.13.3）下载后 POST 落地。';
COMMENT ON COLUMN ods.industry_weight.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.industry_weight.taxonomy IS '分类体系标识，如 swhy（申万宏源）。';
COMMENT ON COLUMN ods.industry_weight.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.industry_weight.index_code IS '行业指数代码；SDK INDEX_CODE。';
COMMENT ON COLUMN ods.industry_weight.con_code IS '成分股代码（含交易所后缀）；SDK CON_CODE。';
COMMENT ON COLUMN ods.industry_weight.symbol IS '证券代码（纯代码，con_code 去交易所后缀）。';
COMMENT ON COLUMN ods.industry_weight.trade_date IS '交易日期；SDK TRADE_DATE。';
COMMENT ON COLUMN ods.industry_weight.weight IS '权重；SDK WEIGHT。';
COMMENT ON COLUMN ods.industry_weight.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.industry_weight.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.industry_daily IS '行业指数日行情（OHLCV + 估值）。ODS 落地表，由 artemis 从 AmazingData get_industry_daily（SWHY 申万，指南 3.5.13.4）下载后 POST 落地。';
COMMENT ON COLUMN ods.industry_daily.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.industry_daily.taxonomy IS '分类体系标识，如 swhy（申万宏源）。';
COMMENT ON COLUMN ods.industry_daily.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.industry_daily.index_code IS '行业指数代码；SDK INDEX_CODE。';
COMMENT ON COLUMN ods.industry_daily.trade_date IS '交易日期；SDK TRADE_DATE。';
COMMENT ON COLUMN ods.industry_daily.open IS '开盘价；SDK OPEN。';
COMMENT ON COLUMN ods.industry_daily.high IS '最高价；SDK HIGH。';
COMMENT ON COLUMN ods.industry_daily.close IS '收盘价；SDK CLOSE。';
COMMENT ON COLUMN ods.industry_daily.low IS '最低价；SDK LOW。';
COMMENT ON COLUMN ods.industry_daily.pre_close IS '昨收盘价；SDK PRE_CLOSE。';
COMMENT ON COLUMN ods.industry_daily.amount IS '成交金额（元）；SDK AMOUNT。';
COMMENT ON COLUMN ods.industry_daily.volume IS '成交量（股）；SDK VOLUME。';
COMMENT ON COLUMN ods.industry_daily.pb IS '指数市净率；SDK PB。';
COMMENT ON COLUMN ods.industry_daily.pe IS '指数市盈率；SDK PE。';
COMMENT ON COLUMN ods.industry_daily.total_cap IS '总市值（万元）；SDK TOTAL_CAP。';
COMMENT ON COLUMN ods.industry_daily.a_float_cap IS 'A 股流通市值（万元）；SDK A_FLOAT_CAP。';
COMMENT ON COLUMN ods.industry_daily.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.industry_daily.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.financial_statement IS '上市公司财务报表（资产负债表/利润表/现金流量表/业绩快报/业绩预告/偿债能力）。多源：AmazingData get_balance_sheet/get_income/get_cash_flow/get_profit_express/get_profit_notice（指南 3.5.2~3.5.5）及 baostock query_balance_data（偿债能力，statement_type=bs_balance）。报表明细字段存 data_json，字段契约见 govern.data_field_dictionary。';
COMMENT ON COLUMN ods.financial_statement.id IS '自增主键。';
COMMENT ON COLUMN ods.financial_statement.source IS '数据源标识，amazing_data / baostock。';
COMMENT ON COLUMN ods.financial_statement.symbol IS '证券代码（纯代码，不含交易所后缀）；来自 SDK MARKET_CODE 去后缀。';
COMMENT ON COLUMN ods.financial_statement.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.financial_statement.statement_type IS '报表类型枚举（PhoenixA 内部，非 SDK 字段）：balance_sheet/income/cashflow/profit_express/profit_notice（AmazingData）及 bs_balance（baostock 偿债能力）。';
COMMENT ON COLUMN ods.financial_statement.reporting_period IS '报告期（YYYY-MM-DD）；SDK REPORTING_PERIOD。';
COMMENT ON COLUMN ods.financial_statement.report_type IS '报告期名称（如一季报/半年报/年报）；SDK REPORT_TYPE。';
COMMENT ON COLUMN ods.financial_statement.statement_code IS '报表类型代码（参看报表类型代码表）；来自 SDK STATEMENT_TYPE 列。';
COMMENT ON COLUMN ods.financial_statement.security_name IS '证券简称；SDK SECURITY_NAME。';
COMMENT ON COLUMN ods.financial_statement.ann_date IS '公告日期；SDK ANN_DATE。';
COMMENT ON COLUMN ods.financial_statement.actual_ann_date IS '实际公告日期；SDK ACTUAL_ANN_DATE。';
COMMENT ON COLUMN ods.financial_statement.comp_type_code IS '公司类型代码（1=非金融类，2=银行，3=保险，4=证券）；SDK COMP_TYPE_CODE。';
COMMENT ON COLUMN ods.financial_statement.data_json IS '报表明细字段 JSONB，内容因 statement_type 而异；字段契约见 govern.data_field_dictionary。';
COMMENT ON COLUMN ods.financial_statement.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.financial_statement.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.corporate_action IS '上市公司公司行为（分红/配股）。ODS 落地表，由 artemis 从 AmazingData get_dividend（指南 3.5.7.1）/ get_right_issue（指南 3.5.7.2）下载后 POST 落地。明细字段存 data_json，字段契约见 govern.data_field_dictionary。';
COMMENT ON COLUMN ods.corporate_action.id IS '自增主键。';
COMMENT ON COLUMN ods.corporate_action.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.corporate_action.symbol IS '证券代码（纯代码，不含交易所后缀）；来自 SDK MARKET_CODE 去后缀。';
COMMENT ON COLUMN ods.corporate_action.market IS '市场标识，如 zh_a。';
COMMENT ON COLUMN ods.corporate_action.action_type IS '公司行为类型枚举（PhoenixA 内部）：dividend（分红）/ right_issue（配股）。';
COMMENT ON COLUMN ods.corporate_action.report_period IS '报告年度；dividend 来自 SDK REPORT_PERIOD（分红年度），right_issue 来自 SDK RIGHTSISSUE_YEAR（配股年度）。';
COMMENT ON COLUMN ods.corporate_action.ann_date IS '公告日期；SDK ANN_DATE。';
COMMENT ON COLUMN ods.corporate_action.progress_code IS '方案进度代码；dividend 来自 SDK DIV_PROGRESS（参看股票分红进度代码表），right_issue 来自 SDK PROGRESS（参看股票配股进度代码表）。';
COMMENT ON COLUMN ods.corporate_action.data_json IS '公司行为明细字段 JSONB；字段契约见 govern.data_field_dictionary。';
COMMENT ON COLUMN ods.corporate_action.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.corporate_action.updated_at IS '记录更新时间。';

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

COMMENT ON TABLE ods.bars_stock_zh_a_daily_nf IS 'A 股日线行情（不复权）。ODS 落地表，由 artemis 从 baostock query_history_k_data_plus（adjustflag=3 不复权）下载后 POST 落地。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.symbol IS '证券代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.trade_date IS '交易所行情日期；baostock date。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.open IS '开盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.high IS '最高价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.low IS '最低价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.close IS '收盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.volume IS '成交量（累计，单位：股）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.amount IS '成交额（单位：人民币元）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.preclose IS '前收盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_nf.pct_chg IS '涨跌幅（%）；baostock pctChg，日涨跌幅=[(收盘价-前收盘价)/前收盘价]*100%。';

-- ──────────────────────────────────────────────────────────
-- 9. bars_stock_zh_a_daily_hfq  (A股日线后复权)
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

COMMENT ON TABLE ods.bars_stock_zh_a_daily_hfq IS 'A 股日线行情（后复权）。ODS 落地表，由 artemis 从 baostock query_history_k_data_plus（adjustflag=1 后复权）下载后 POST 落地。BaoStock 采用涨跌幅复权法。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.symbol IS '证券代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.trade_date IS '交易所行情日期；baostock date。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.open IS '开盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.high IS '最高价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.low IS '最低价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.close IS '收盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.volume IS '成交量（累计，单位：股）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.amount IS '成交额（单位：人民币元）。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.preclose IS '前收盘价。';
COMMENT ON COLUMN ods.bars_stock_zh_a_daily_hfq.pct_chg IS '涨跌幅（%）；baostock pctChg，日涨跌幅=[(收盘价-前收盘价)/前收盘价]*100%。';

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

COMMENT ON TABLE ods.bars_index_zh_a_daily_nf IS 'A 股指数日线行情（不复权）。ODS 落地表，由 artemis 从 baostock query_history_k_data_plus（指数代码，adjustflag=3 不复权）下载后 POST 落地。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.symbol IS '指数代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.trade_date IS '交易所行情日期；baostock date。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.open IS '开盘价。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.high IS '最高价。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.low IS '最低价。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.close IS '收盘价。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.volume IS '成交量（累计，单位：股）。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.amount IS '成交额（单位：人民币元）。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.preclose IS '前收盘价。';
COMMENT ON COLUMN ods.bars_index_zh_a_daily_nf.pct_chg IS '涨跌幅（%）；baostock pctChg，日涨跌幅=[(收盘价-前收盘价)/前收盘价]*100%。';

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

COMMENT ON TABLE ods.bars_ext_baostock_stock_zh_a_daily IS 'A 股日线扩展指标（换手率 + 估值指标）。ODS 落地表，由 artemis 从 baostock query_history_k_data_plus 扩展字段下载后 POST 落地，与 bars_stock_zh_a_daily_* 同源同日但拆表存储。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.symbol IS '证券代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.trade_date IS '交易所行情日期；baostock date。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.turn IS '换手率（%）；baostock turn，=[当日成交量/当日流通股总股数]*100%。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.pe_ttm IS '滚动市盈率；baostock peTTM，=收盘价/每股盈余TTM。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.ps_ttm IS '滚动市销率；baostock psTTM，=收盘价/每股销售额TTM。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.pb_mrq IS '市净率；baostock pbMRQ，=收盘价/每股净资产（最近披露）。';
COMMENT ON COLUMN ods.bars_ext_baostock_stock_zh_a_daily.pcf_ncf_ttm IS '滚动市现率；baostock pcfNcfTTM，=收盘价/每股现金流TTM。';

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

COMMENT ON TABLE ods.adjust_factor IS '复权因子。ODS 落地表，由 artemis 从 baostock query_adjust_factor 下载后 POST 落地。';
COMMENT ON COLUMN ods.adjust_factor.id IS '自增主键。';
COMMENT ON COLUMN ods.adjust_factor.source IS '数据源标识，固定 baostock。';
COMMENT ON COLUMN ods.adjust_factor.symbol IS '证券代码（纯代码，不含交易所后缀）。';
COMMENT ON COLUMN ods.adjust_factor.market IS '市场标识，固定 zh_a。';
COMMENT ON COLUMN ods.adjust_factor.divid_operate_date IS '除权除息日期；baostock dividOperateDate。';
COMMENT ON COLUMN ods.adjust_factor.fore_adjust_factor IS '向前复权因子；baostock foreAdjustFactor。';
COMMENT ON COLUMN ods.adjust_factor.back_adjust_factor IS '向后复权因子；baostock backAdjustFactor。';
COMMENT ON COLUMN ods.adjust_factor.adjust_factor IS '本次复权因子；baostock adjustFactor。';

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

COMMENT ON TABLE ods.long_hu_bang IS '龙虎榜数据。ODS 落地表，由 artemis 从 AmazingData get_long_hu_bang（指南 3.5.9.1）下载后 POST 落地。';
COMMENT ON COLUMN ods.long_hu_bang.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN ods.long_hu_bang.symbol IS '证券代码（纯代码，不含交易所后缀）；来自 SDK MARKET_CODE 去后缀。';
COMMENT ON COLUMN ods.long_hu_bang.market IS '市场标识，固定 zh_a。';
COMMENT ON COLUMN ods.long_hu_bang.trade_date IS '交易日期；SDK TRADE_DATE。';
COMMENT ON COLUMN ods.long_hu_bang.security_name IS '证券名称；SDK SECURITY_NAME。';
COMMENT ON COLUMN ods.long_hu_bang.reason_type IS '上榜原因类型；SDK REASON_TYPE。';
COMMENT ON COLUMN ods.long_hu_bang.reason_type_name IS '上榜原因；SDK REASON_TYPE_NAME。';
COMMENT ON COLUMN ods.long_hu_bang.trader_name IS '营业部名称；SDK TRADER_NAME。';
COMMENT ON COLUMN ods.long_hu_bang.flow_mark IS '买卖标识；SDK FLOW_MARK，1=买入，2=卖出。';
COMMENT ON COLUMN ods.long_hu_bang.change_range IS '涨跌幅（%）；SDK CHANGE_RANGE。';
COMMENT ON COLUMN ods.long_hu_bang.buy_amount IS '买入金额（元）；SDK BUY_AMOUNT。';
COMMENT ON COLUMN ods.long_hu_bang.sell_amount IS '卖出金额（元）；SDK SELL_AMOUNT。';
COMMENT ON COLUMN ods.long_hu_bang.total_amount IS '实际交易金额（元）；SDK TOTAL_AMOUNT。';
COMMENT ON COLUMN ods.long_hu_bang.total_volume IS '实际交易量（万股）；SDK TOTAL_VOLUME。';

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
    id           BIGSERIAL      PRIMARY KEY,
    exchange     VARCHAR(8)     NOT NULL,
    asset_type   VARCHAR(16)    NOT NULL,
    symbol       VARCHAR(32)    NOT NULL,
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    name         VARCHAR(128)   NOT NULL DEFAULT '',
    full_name    VARCHAR(256),
    status       VARCHAR(16)    NOT NULL DEFAULT 'active',
    list_date    DATE,
    delist_date  DATE,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_sr_exchange_asset_symbol UNIQUE (exchange, asset_type, symbol)
) TABLESPACE pg_default;

-- idx_sr_exchange 已删除：uk_sr_exchange_asset_symbol 唯一约束索引以 exchange 为前导列，已覆盖按 exchange 的查询。
CREATE INDEX IF NOT EXISTS idx_sr_asset_market
    ON ods.security_registry (asset_type, market);
CREATE INDEX IF NOT EXISTS idx_sr_status
    ON ods.security_registry (status)
    WHERE status != 'active';

COMMENT ON TABLE ods.security_registry IS '统一证券注册表（股票/ETF/指数基础信息）。代理主键 id (BIGSERIAL) 是 (exchange, asset_type, symbol) 自然键的代理，作为其他表逻辑外键 security_id 的引用目标（不建真实 FK 约束）。单一外部来源：artemis 从 AmazingData get_code_info 下载，POST /api/v2/securities/upsert 按自然键 upsert（id 自增）。单源主数据，无 source 列。';
COMMENT ON COLUMN ods.security_registry.id IS '代理主键 (BIGSERIAL)，仅在当前重建周期内稳定；是 (exchange, asset_type, symbol) 自然键的代理，被其他表 security_id 逻辑引用。';
COMMENT ON COLUMN ods.security_registry.exchange IS '交易所（SH/SZ/BJ 大写），由代码后缀派生，phoenixA 落库时统一 ToUpper；与 asset_type、symbol 共同构成自然唯一键。';
COMMENT ON COLUMN ods.security_registry.asset_type IS '资产类型，当前固定为 stock；与 exchange、symbol 共同构成自然唯一键。';
COMMENT ON COLUMN ods.security_registry.symbol IS '证券代码（纯代码，不含交易所后缀）；来自 AmazingData get_code_info；与 exchange、asset_type 共同构成自然唯一键。';
COMMENT ON COLUMN ods.security_registry.market IS '市场标识（普通属性列，不参与自然唯一键），当前固定为 zh_a。';
COMMENT ON COLUMN ods.security_registry.name IS '证券简称；来自 get_code_info 的 symbol 列。';
COMMENT ON COLUMN ods.security_registry.full_name IS '证券全称（预留字段，当前无数据源填充）。';
COMMENT ON COLUMN ods.security_registry.status IS '证券状态，当前固定为 active。';
COMMENT ON COLUMN ods.security_registry.list_date IS '上市日期（预留字段，当前无数据源填充）。';
COMMENT ON COLUMN ods.security_registry.delist_date IS '退市日期（预留字段，当前无数据源填充）。';
COMMENT ON COLUMN ods.security_registry.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.security_registry.updated_at IS '记录更新时间。';
