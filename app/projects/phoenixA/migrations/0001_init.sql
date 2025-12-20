-- 0001_init.sql
-- phoenixA initial schema
-- Stock list table
-- Requirements:
-- 1) code: fixed 6-digit string, primary key
-- 2) no soft delete / no hard delete column
-- 3) no created_at / updated_at
-- 4) no id
-- 5) exchange: fixed length 2 (SH/SZ/BJ)

CREATE TABLE IF NOT EXISTS stock_zh_a_list (
    code CHAR(6) NOT NULL COMMENT 'A-share stock code (6 digits)',
    company VARCHAR(8) NOT NULL DEFAULT '' COMMENT 'company/stock name',
    exchange CHAR(2) NOT NULL COMMENT 'SH/SZ/BJ',
    PRIMARY KEY (code),
    KEY idx_exchange (exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
