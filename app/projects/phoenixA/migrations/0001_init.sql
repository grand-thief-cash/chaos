-- ============================================================
-- PhoenixA Unified Migration (idempotent)
-- Consolidates all schema (0001-0007) into a single file.
-- Safe to re-run on every app startup.
--
-- Fresh install: creates v2 tables directly.
-- Upgrade from v1: migrates data, then archives old tables.
-- ============================================================


-- ============================================================
-- PART 1: CREATE TABLES
-- ============================================================

-- 1.1 Security Registry (replaces stock_zh_a_list)
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

-- 1.2 Bars Tables (replaces stock_zh_a_hist_*)
--    Naming: bars_{asset_type}_{market}_{period}_{adjust}
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

CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_hfq LIKE bars_stock_zh_a_daily_nf;

CREATE TABLE IF NOT EXISTS bars_index_zh_a_daily_nf LIKE bars_stock_zh_a_daily_nf;

-- 1.3 Bars Extension Tables
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

-- 1.4 Taxonomy Tables (replaces mkt_category_*, category_stock_map)
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

-- 1.5 Strategy Run Tables (fresh install uses 'period', upgrade handled in PART 3)
CREATE TABLE IF NOT EXISTS strategy_run_summary (
    run_id VARCHAR(128) NOT NULL COMMENT '回测运行唯一标识',
    parent_run_id VARCHAR(128) NULL COMMENT '父级 Campaign 运行 ID',
    task_code VARCHAR(64) NOT NULL COMMENT '任务类型代码',
    mode VARCHAR(32) NOT NULL COMMENT '回测模式',
    strategy_code VARCHAR(64) NOT NULL COMMENT '策略代码',
    symbol VARCHAR(32) NOT NULL COMMENT '股票代码',
    period VARCHAR(32) NOT NULL COMMENT 'K线周期',
    start_date DATE NULL COMMENT '回测起始日期',
    end_date DATE NULL COMMENT '回测结束日期',
    start_cash DECIMAL(20,4) NULL COMMENT '初始资金',
    end_value DECIMAL(20,4) NULL COMMENT '期末总资产',
    pnl DECIMAL(20,4) NULL COMMENT '盈亏金额',
    pnl_pct DECIMAL(20,6) NULL COMMENT '盈亏百分比',
    max_drawdown DECIMAL(20,6) NULL COMMENT '最大回撤',
    sharpe DECIMAL(20,6) NULL COMMENT '夏普比率',
    trade_count INT NOT NULL DEFAULT 0 COMMENT '总交易次数',
    win_count INT NOT NULL DEFAULT 0 COMMENT '盈利交易次数',
    loss_count INT NOT NULL DEFAULT 0 COMMENT '亏损交易次数',
    win_rate DECIMAL(20,6) NULL COMMENT '胜率',
    bars_processed INT NOT NULL DEFAULT 0 COMMENT '处理的K线数量',
    status VARCHAR(32) NOT NULL COMMENT '运行状态',
    stop_reason VARCHAR(128) NULL COMMENT '停止原因',
    error_message TEXT NULL COMMENT '错误信息',
    duration_ms BIGINT NOT NULL DEFAULT 0 COMMENT '执行耗时(ms)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (run_id),
    KEY idx_strategy_run_summary_parent_run_id (parent_run_id),
    KEY idx_strategy_run_summary_strategy_code (strategy_code),
    KEY idx_strategy_run_summary_symbol (symbol),
    KEY idx_strategy_run_summary_status (status),
    KEY idx_strategy_run_summary_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略回测汇总结果表';

CREATE TABLE IF NOT EXISTS strategy_run_artifact (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    run_id VARCHAR(128) NOT NULL COMMENT '关联的回测运行 ID',
    artifact_type VARCHAR(64) NOT NULL COMMENT '制品类型',
    payload_json LONGTEXT NOT NULL COMMENT '制品 JSON 数据',
    payload_version VARCHAR(32) NOT NULL COMMENT '数据格式版本',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_strategy_run_artifact_run_type (run_id, artifact_type),
    KEY idx_strategy_run_artifact_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略回测制品数据表';


-- ============================================================
-- PART 2: DATA MIGRATION (v1 -> v2, only if v1 tables exist)
-- ============================================================

-- Helper: check both TABLE existence AND required COLUMN existence.
-- Prevents errors when a table exists but its schema differs from expectations
-- (e.g. mkt_category_swhy uses industry_code, not code).

-- 2.1 stock_zh_a_list -> security_registry
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_list');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_list' AND COLUMN_NAME = 'code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO security_registry (symbol, asset_type, market, exchange, name) SELECT code, ''stock'', ''zh_a'', exchange, company FROM stock_zh_a_list', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.2 stock_zh_a_hist_daily_nf -> bars_stock_zh_a_daily_nf
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf' AND COLUMN_NAME = 'code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO bars_stock_zh_a_daily_nf (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg) SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg FROM stock_zh_a_hist_daily_nf', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.3 stock_zh_a_hist_daily_nf -> bars_ext_baostock_stock_zh_a_daily (extension columns)
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf' AND COLUMN_NAME = 'code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO bars_ext_baostock_stock_zh_a_daily (symbol, trade_date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm) SELECT code, date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm FROM stock_zh_a_hist_daily_nf WHERE (turn IS NOT NULL AND turn != 0) OR (pe_ttm IS NOT NULL AND pe_ttm != 0) OR (ps_ttm IS NOT NULL AND ps_ttm != 0) OR (pb_mrq IS NOT NULL AND pb_mrq != 0) OR (pcf_ncf_ttm IS NOT NULL AND pcf_ncf_ttm != 0)', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.4 stock_zh_a_hist_daily_hfq -> bars_stock_zh_a_daily_hfq
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_hfq');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_hfq' AND COLUMN_NAME = 'code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO bars_stock_zh_a_daily_hfq (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg) SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg FROM stock_zh_a_hist_daily_hfq', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.5 mkt_category_mairui -> taxonomy_category
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_mairui');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_mairui' AND COLUMN_NAME = 'code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO taxonomy_category (source, code, name, parent_code, level, is_leaf, attrs_json) SELECT ''mairui'', code, name, parent_code, level, is_leaf, JSON_OBJECT(''parent_name'', parent_name, ''type1'', type1, ''type2'', type2) FROM mkt_category_mairui', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.6 category_stock_map -> taxonomy_security_map
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'category_stock_map');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'category_stock_map' AND COLUMN_NAME = 'stock_code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO taxonomy_security_map (source, category_code, symbol, asset_type, market) SELECT ''mairui'', category_code, stock_code, ''stock'', ''zh_a'' FROM category_stock_map', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.7 mkt_category_swhy -> taxonomy_category
-- NOTE: mkt_category_swhy schema differs from mairui — uses industry_code, not code.
SET @src_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_swhy');
SET @col_exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_swhy' AND COLUMN_NAME = 'industry_code');
SET @mig_sql = IF(@src_exist > 0 AND @col_exist > 0, 'INSERT IGNORE INTO taxonomy_category (source, code, name, parent_code, level, is_leaf, attrs_json) SELECT ''swhy'', industry_code, CASE level_type WHEN 1 THEN level1_name WHEN 2 THEN level2_name WHEN 3 THEN level3_name END, NULL, level_type, 1, JSON_OBJECT(''index_code'', index_code, ''level1_name'', level1_name, ''level2_name'', level2_name, ''level3_name'', level3_name, ''is_pub'', is_pub, ''change_reason'', change_reason) FROM mkt_category_swhy', 'SELECT 1');
PREPARE stmt FROM @mig_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- ============================================================
-- PART 3: COLUMN RENAME - strategy_run_summary.timeframe -> period
--   Only runs if the old column name still exists.
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'strategy_run_summary' AND COLUMN_NAME = 'timeframe');
SET @alter_sql = IF(@col_exists > 0, 'ALTER TABLE strategy_run_summary CHANGE COLUMN timeframe period VARCHAR(32) NOT NULL COMMENT ''K线周期''', 'SELECT 1');
PREPARE stmt FROM @alter_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- ============================================================
-- PART 4: ARCHIVE OLD TABLES
--   Only renames if old table exists AND _archive does not.
-- ============================================================

-- 4.1 stock_zh_a_list
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_list');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_list_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE stock_zh_a_list TO stock_zh_a_list_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4.2 stock_zh_a_hist_daily_nf
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_nf_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE stock_zh_a_hist_daily_nf TO stock_zh_a_hist_daily_nf_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4.3 stock_zh_a_hist_daily_hfq
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_hfq');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_zh_a_hist_daily_hfq_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE stock_zh_a_hist_daily_hfq TO stock_zh_a_hist_daily_hfq_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4.4 mkt_category_mairui
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_mairui');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_mairui_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE mkt_category_mairui TO mkt_category_mairui_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4.5 category_stock_map
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'category_stock_map');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'category_stock_map_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE category_stock_map TO category_stock_map_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4.6 mkt_category_swhy (if exists)
SET @old_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_swhy');
SET @arch_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mkt_category_swhy_archive');
SET @rename_sql = IF(@old_exists > 0 AND @arch_exists = 0, 'RENAME TABLE mkt_category_swhy TO mkt_category_swhy_archive', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
