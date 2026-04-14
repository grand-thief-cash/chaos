-- 0005_v2_architecture.sql
-- PhoenixA v2 architecture: unified data platform schema
-- Replaces: stock_zh_a_list, stock_zh_a_hist_*, mkt_category_*, category_stock_map

-- ============================================================
-- 1. Security Registry (replaces stock_zh_a_list)
-- ============================================================
CREATE TABLE IF NOT EXISTS security_registry (
    symbol       VARCHAR(32)   NOT NULL COMMENT '证券代码',
    asset_type   VARCHAR(16)   NOT NULL COMMENT 'stock/index/etf/futures/fund/cb',
    market       VARCHAR(16)   NOT NULL COMMENT 'zh_a/hk/us/global',
    exchange     VARCHAR(8)    NOT NULL COMMENT 'SH/SZ/BJ/HKEX/NYSE/...',
    name         VARCHAR(128)  NOT NULL DEFAULT '' COMMENT '证券简称',
    full_name    VARCHAR(256)  NULL     COMMENT '证券全称',
    status       VARCHAR(16)   NOT NULL DEFAULT 'active' COMMENT 'active/delisted/suspended',
    list_date    DATE          NULL     COMMENT '上市日期',
    delist_date  DATE          NULL     COMMENT '退市日期',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, asset_type, market),
    KEY idx_asset_market (asset_type, market),
    KEY idx_exchange (exchange),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一证券注册表';

-- Migrate existing data: stock_zh_a_list -> security_registry
-- INSERT IGNORE INTO security_registry (symbol, asset_type, market, exchange, name)
-- SELECT code, 'stock', 'zh_a', exchange, company FROM stock_zh_a_list;


-- ============================================================
-- 2. Standard Bars Tables (replaces stock_zh_a_hist_*)
--    Naming: bars_{asset_type}_{market}_{period}_{adjust}
--    Fields unified: symbol (was code), trade_date (was date)
-- ============================================================

-- DAILY NO-ADJUST (NF) - Stock A-shares
CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_nf (
    symbol      VARCHAR(32)    NOT NULL COMMENT '证券代码',
    trade_date  DATE           NOT NULL COMMENT '交易日',
    open        DECIMAL(20,4)  NULL     COMMENT '开盘价',
    high        DECIMAL(20,4)  NULL     COMMENT '最高价',
    low         DECIMAL(20,4)  NULL     COMMENT '最低价',
    close       DECIMAL(20,4)  NULL     COMMENT '收盘价',
    volume      BIGINT         NULL     COMMENT '成交量',
    amount      BIGINT         NULL     COMMENT '成交额',
    preclose    DECIMAL(20,4)  NULL     COMMENT '昨收价',
    pct_chg     DECIMAL(10,4)  NULL     COMMENT '涨跌幅(%)',
    PRIMARY KEY (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A股日线行情(不复权)'
    PARTITION BY RANGE (YEAR(trade_date)) (
    PARTITION p2008 VALUES LESS THAN (2009),
    PARTITION p2009 VALUES LESS THAN (2010),
    PARTITION p2010 VALUES LESS THAN (2011),
    PARTITION p2011 VALUES LESS THAN (2012),
    PARTITION p2012 VALUES LESS THAN (2013),
    PARTITION p2013 VALUES LESS THAN (2014),
    PARTITION p2014 VALUES LESS THAN (2015),
    PARTITION p2015 VALUES LESS THAN (2016),
    PARTITION p2016 VALUES LESS THAN (2017),
    PARTITION p2017 VALUES LESS THAN (2018),
    PARTITION p2018 VALUES LESS THAN (2019),
    PARTITION p2019 VALUES LESS THAN (2020),
    PARTITION p2020 VALUES LESS THAN (2021),
    PARTITION p2021 VALUES LESS THAN (2022),
    PARTITION p2022 VALUES LESS THAN (2023),
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p2027 VALUES LESS THAN (2028)
);

-- DAILY BACKWARD-ADJUST (HFQ) - Stock A-shares
CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_hfq LIKE bars_stock_zh_a_daily_nf;

-- DAILY NO-ADJUST (NF) - Index A-shares
CREATE TABLE IF NOT EXISTS bars_index_zh_a_daily_nf LIKE bars_stock_zh_a_daily_nf;


-- ============================================================
-- 3. Bars Extension Tables (source-specific extra columns)
--    Naming: bars_ext_{source}_{asset_type}_{market}_{period}
-- ============================================================

CREATE TABLE IF NOT EXISTS bars_ext_baostock_stock_zh_a_daily (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    turn        DECIMAL(10,4)  NULL     COMMENT '换手率(%)',
    pe_ttm      DECIMAL(20,4)  NULL     COMMENT '滚动市盈率',
    ps_ttm      DECIMAL(20,4)  NULL     COMMENT '滚动市销率',
    pb_mrq      DECIMAL(20,4)  NULL     COMMENT '市净率(MRQ)',
    pcf_ncf_ttm DECIMAL(20,4)  NULL     COMMENT '滚动市现率',
    PRIMARY KEY (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='baostock A股日线扩展指标';


-- ============================================================
-- 4. Taxonomy (replaces mkt_category_mairui, mkt_category_swhy, category_stock_map)
-- ============================================================

CREATE TABLE IF NOT EXISTS taxonomy_category (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)   NOT NULL COMMENT '分类来源: mairui/swhy/citic/gics/concept/region',
    code         VARCHAR(64)   NOT NULL COMMENT '分类代码（source 内唯一）',
    name         VARCHAR(255)  NOT NULL COMMENT '分类名称',
    parent_code  VARCHAR(64)   NULL     COMMENT '父分类代码',
    level        TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '层级',
    is_leaf      TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否叶子节点',
    attrs_json   JSON          NULL     COMMENT '来源特有属性',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_source_code (source, code),
    KEY idx_parent (source, parent_code),
    KEY idx_level (source, level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一分类节点表';

CREATE TABLE IF NOT EXISTS taxonomy_security_map (
    source        VARCHAR(32) NOT NULL COMMENT '分类来源',
    category_code VARCHAR(64) NOT NULL COMMENT '分类代码',
    symbol        VARCHAR(32) NOT NULL COMMENT '证券代码',
    asset_type    VARCHAR(16) NOT NULL DEFAULT 'stock' COMMENT '资产类型',
    market        VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    UNIQUE KEY uk_source_cat_sec (source, category_code, symbol, asset_type, market),
    KEY idx_symbol (symbol, asset_type, market),
    KEY idx_category (source, category_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一分类-证券关系表';


-- ============================================================
-- 5. Data migration scripts (run manually after verifying)
-- ============================================================

-- Migrate stock_zh_a_list -> security_registry
-- INSERT IGNORE INTO security_registry (symbol, asset_type, market, exchange, name)
-- SELECT code, 'stock', 'zh_a', exchange, company FROM stock_zh_a_list;

-- Migrate stock_zh_a_hist_daily_nf -> bars_stock_zh_a_daily_nf
-- INSERT IGNORE INTO bars_stock_zh_a_daily_nf (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg)
-- SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg FROM stock_zh_a_hist_daily_nf;

-- Migrate baostock extension columns
-- INSERT IGNORE INTO bars_ext_baostock_stock_zh_a_daily (symbol, trade_date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm)
-- SELECT code, date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm FROM stock_zh_a_hist_daily_nf
-- WHERE turn != 0 OR pe_ttm != 0 OR ps_ttm != 0 OR pb_mrq != 0 OR pcf_ncf_ttm != 0;

-- Migrate stock_zh_a_hist_daily_hfq -> bars_stock_zh_a_daily_hfq
-- INSERT IGNORE INTO bars_stock_zh_a_daily_hfq (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg)
-- SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg FROM stock_zh_a_hist_daily_hfq;

-- Migrate mkt_category_mairui -> taxonomy_category
-- INSERT IGNORE INTO taxonomy_category (source, code, name, parent_code, level, is_leaf, attrs_json)
-- SELECT 'mairui', code, name, parent_code, level, is_leaf,
--        JSON_OBJECT('parent_name', parent_name, 'type1', type1, 'type2', type2)
-- FROM mkt_category_mairui;

-- Migrate category_stock_map -> taxonomy_security_map
-- INSERT IGNORE INTO taxonomy_security_map (source, category_code, symbol, asset_type, market)
-- SELECT 'mairui', category_code, stock_code, 'stock', 'zh_a' FROM category_stock_map;

