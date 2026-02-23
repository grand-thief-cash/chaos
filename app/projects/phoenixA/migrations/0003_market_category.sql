CREATE TABLE IF NOT EXISTS mkt_category_mairui (
 code        VARCHAR(64)  NOT NULL COMMENT '分类代码，唯一',
 name        VARCHAR(255) NOT NULL COMMENT '分类名称',
 parent_code VARCHAR(64)  DEFAULT NULL COMMENT '父节点代码',
 parent_name VARCHAR(255) DEFAULT NULL COMMENT '父节点名称',
 level       TINYINT UNSIGNED NOT NULL COMMENT '层级，从0开始',
 type1       TINYINT UNSIGNED NOT NULL COMMENT '一级分类',
 type2       SMALLINT UNSIGNED NOT NULL COMMENT '二级分类',
 is_leaf     TINYINT(1) NOT NULL COMMENT '是否叶子节点 1=是',
 UNIQUE KEY uk_code (code),
 KEY idx_parent_code (parent_code),
 KEY idx_type (type1, type2),
 KEY idx_level (level),
 KEY idx_is_leaf (is_leaf)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE IF NOT EXISTS category_stock_map (
category_code VARCHAR(64) NOT NULL COMMENT '分类代码',
stock_code    VARCHAR(6) NOT NULL COMMENT '股票代码',
UNIQUE KEY uk_cat_stock (category_code, stock_code),
KEY idx_stock (stock_code),
KEY idx_category (category_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='分类-股票关系表';