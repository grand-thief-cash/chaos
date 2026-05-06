-- ============================================================
-- PhoenixA Migration 0002: Taxonomy V2
-- Drops and recreates taxonomy/industry tables with:
--   - taxonomy field (classification system: swhy/citic/gics)
--   - market field (zh_a/us/jp/hk)
--   - index_code on taxonomy_category
--   - symbol on industry_constituent/weight (pure code, joins security_registry)
-- ============================================================

-- Drop old tables (user confirmed: no data preservation needed)
DROP TABLE IF EXISTS taxonomy_security_map;
DROP TABLE IF EXISTS industry_weight;
DROP TABLE IF EXISTS industry_daily;
DROP TABLE IF EXISTS industry_constituent;
DROP TABLE IF EXISTS taxonomy_category;

-- 1. taxonomy_category
CREATE TABLE IF NOT EXISTS taxonomy_category (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)   NOT NULL COMMENT '数据供应商: amazing_data/mairui/tushare',
    taxonomy     VARCHAR(32)   NOT NULL COMMENT '分类体系: swhy/citic/gics/concept/region/mairui',
    market       VARCHAR(16)   NOT NULL DEFAULT 'zh_a' COMMENT '市场: zh_a/us/jp/hk',
    code         VARCHAR(64)   NOT NULL COMMENT '分类代码（体系内唯一，如 INDUSTRY_CODE）',
    name         VARCHAR(255)  NOT NULL COMMENT '分类名称',
    parent_code  VARCHAR(64)   NULL     COMMENT '父分类代码',
    index_code   VARCHAR(64)   NULL     COMMENT '关联行业指数代码（如 801010.SI）',
    level        TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '层级',
    is_leaf      TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否叶子节点',
    attrs_json   JSON          NULL     COMMENT '来源特有属性',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_src_tax_mkt_code (source, taxonomy, market, code),
    KEY idx_parent (source, taxonomy, market, parent_code),
    KEY idx_level (source, taxonomy, market, level),
    KEY idx_index_code (source, taxonomy, index_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一分类节点表 v2';

-- 2. taxonomy_security_map
CREATE TABLE IF NOT EXISTS taxonomy_security_map (
    source        VARCHAR(32) NOT NULL COMMENT '数据供应商',
    taxonomy      VARCHAR(32) NOT NULL COMMENT '分类体系',
    category_code VARCHAR(64) NOT NULL COMMENT '分类代码',
    symbol        VARCHAR(32) NOT NULL COMMENT '证券代码',
    asset_type    VARCHAR(16) NOT NULL DEFAULT 'stock' COMMENT '资产类型',
    market        VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    UNIQUE KEY uk_src_tax_cat_sec (source, taxonomy, category_code, symbol, asset_type, market),
    KEY idx_symbol (symbol, asset_type, market),
    KEY idx_category (source, taxonomy, category_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一分类-证券关系表 v2';

-- 3. industry_constituent
CREATE TABLE IF NOT EXISTS industry_constituent (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)   NOT NULL COMMENT '数据供应商: amazing_data/tushare',
    taxonomy     VARCHAR(32)   NOT NULL COMMENT '分类体系: swhy/citic/gics',
    market       VARCHAR(16)   NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    index_code   VARCHAR(64)   NOT NULL COMMENT '行业指数代码',
    con_code     VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '成分股原始代码(SDK返回值)',
    symbol       VARCHAR(32)   NOT NULL COMMENT '成分股代码(纯symbol, 关联security_registry)',
    index_name   VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '行业指数名称',
    in_date      VARCHAR(10)   NULL     COMMENT '纳入日期',
    out_date     VARCHAR(10)   NULL     COMMENT '剔除日期',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_src_tax_idx_sym (source, taxonomy, index_code, symbol, market),
    KEY idx_index_code (source, taxonomy, index_code),
    KEY idx_symbol (symbol, market)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行业指数成分股表 v2';

-- 4. industry_weight
CREATE TABLE IF NOT EXISTS industry_weight (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)   NOT NULL COMMENT '数据供应商',
    taxonomy     VARCHAR(32)   NOT NULL COMMENT '分类体系',
    market       VARCHAR(16)   NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    index_code   VARCHAR(64)   NOT NULL COMMENT '行业指数代码',
    con_code     VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '成分股原始代码',
    symbol       VARCHAR(32)   NOT NULL COMMENT '成分股代码(纯symbol)',
    trade_date   VARCHAR(10)   NOT NULL COMMENT '交易日期',
    weight       DECIMAL(10,6) NULL     COMMENT '权重(%)',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_src_tax_idx_sym_dt (source, taxonomy, index_code, symbol, market, trade_date),
    KEY idx_index_date (source, taxonomy, index_code, trade_date),
    KEY idx_symbol_date (symbol, market, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行业指数成分股每日权重表 v2';

-- 5. industry_daily
CREATE TABLE IF NOT EXISTS industry_daily (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)    NOT NULL COMMENT '数据供应商',
    taxonomy     VARCHAR(32)    NOT NULL COMMENT '分类体系',
    market       VARCHAR(16)    NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    index_code   VARCHAR(64)    NOT NULL COMMENT '行业指数代码',
    trade_date   VARCHAR(10)    NOT NULL COMMENT '交易日期',
    open         DECIMAL(20,4)  NULL     COMMENT '开盘价',
    high         DECIMAL(20,4)  NULL     COMMENT '最高价',
    close        DECIMAL(20,4)  NULL     COMMENT '收盘价',
    low          DECIMAL(20,4)  NULL     COMMENT '最低价',
    pre_close    DECIMAL(20,4)  NULL     COMMENT '昨收盘价',
    amount       DECIMAL(20,4)  NULL     COMMENT '成交金额(元)',
    volume       DECIMAL(20,4)  NULL     COMMENT '成交量(股)',
    pb           DECIMAL(20,4)  NULL     COMMENT '指数市净率',
    pe           DECIMAL(20,4)  NULL     COMMENT '指数市盈率',
    total_cap    DECIMAL(20,4)  NULL     COMMENT '总市值(万元)',
    a_float_cap  DECIMAL(20,4)  NULL     COMMENT 'A股流通市值(万元)',
    created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_src_tax_idx_mkt_dt (source, taxonomy, index_code, market, trade_date),
    KEY idx_index_date (source, taxonomy, index_code, trade_date),
    KEY idx_trade_date (source, taxonomy, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行业指数日行情表 v2';

