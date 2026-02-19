-- 0002_stock_hist.sql
-- Stock History Tables
-- Design Principles:
-- 1. Separated by Frequency and Adjustment to avoid redundant columns.
-- 2. Code is CHAR(6) to match stock_zh_a_list.
-- 3. Decimals limited to 2 places where possible.
-- 4. Removed adjustflag column.

-- ========================================================
-- DAILY DATA (Daily)
-- Fields: date, code, open, high, low, close, preclose, volume, amount, turn, tradestatus, pctChg, peTTM, psTTM, pcfNcfTTM, pbMRQ
-- adjustments: nf (No), qfq (Forward), hfq (Backward)
-- ========================================================

-- DAILY NO-ADJUST (NF)
-- Partitioning by YEAR for daily tables is recommended for scalability.
-- However, dynamic partitioning is complex.
-- Assuming standard RANGE partitioning on `date`.
CREATE TABLE IF NOT EXISTS stock_zh_a_hist_daily_nf (
    date DATE NOT NULL,
    code CHAR(6) NOT NULL,
    open DECIMAL(20,2),
    high DECIMAL(20,2),
    low DECIMAL(20,2),
    close DECIMAL(20,2),
    preclose DECIMAL(20,2),
    volume BIGINT,
    amount BIGINT,
    turn DECIMAL(20,2),
    pct_chg DECIMAL(20,2),
    pe_ttm DECIMAL(20,2),
    ps_ttm DECIMAL(20,2),
    pcf_ncf_ttm DECIMAL(20,2),
    pb_mrq DECIMAL(20,2),
    PRIMARY KEY (code, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    PARTITION BY RANGE (YEAR(date)) (
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
    PARTITION p2026 VALUES LESS THAN (2027)
);

-- DAILY FORWARD-ADJUST (QFQ)
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_daily_qfq LIKE stock_zh_a_hist_daily_nf;

-- DAILY BACKWARD-ADJUST (HFQ)
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_daily_hfq LIKE stock_zh_a_hist_daily_nf;


-- ========================================================
-- WEEKLY/MONTHLY DATA
-- Fields: date, code, open, high, low, close, volume, amount, turn, pctChg
-- NOTE: Tables below are defined but not actively used or partitioned in this iteration.
-- ========================================================

-- WEEKLY NO-ADJUST
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_weekly_nf (
--     date DATE NOT NULL,
--     code CHAR(6) NOT NULL,
--     open DECIMAL(20,2),
--     high DECIMAL(20,2),
--     low DECIMAL(20,2),
--     close DECIMAL(20,2),
--     volume BIGINT,
--     amount BIGINT,
--     turn DECIMAL(20,2),
--     pct_chg DECIMAL(20,2),
--     PRIMARY KEY (code, date)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_weekly_qfq LIKE stock_zh_a_hist_weekly_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_weekly_hfq LIKE stock_zh_a_hist_weekly_nf;

-- MONTHLY NO-ADJUST
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_monthly_nf LIKE stock_zh_a_hist_weekly_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_monthly_qfq LIKE stock_zh_a_hist_weekly_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_monthly_hfq LIKE stock_zh_a_hist_weekly_nf;


-- ========================================================
-- MINUTE DATA (5, 15, 30, 60)
-- Fields: date, time, code, open, high, low, close, volume, amount
-- Note: 'time' format per requirements is YYYYMMDDHHMMSSsss but usually stored as BIGINT or customized string.
-- Since it often acts as the distinct sorted key with date, we can use a composite.
-- Requirement says format: YYYYMMDDHHMMSSsss
-- ========================================================

-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min5_nf (
--     date DATE NOT NULL,
--     time VARCHAR(20) NOT NULL COMMENT 'YYYYMMDDHHMMSSsss',
--     code CHAR(6) NOT NULL,
--     open DECIMAL(20,2),
--     high DECIMAL(20,2),
--     low DECIMAL(20,2),
--     close DECIMAL(20,2),
--     volume BIGINT,
--     amount BIGINT,
--     PRIMARY KEY (code, date, time)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
--
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min5_qfq LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min5_hfq LIKE stock_zh_a_hist_min5_nf;

-- 15 Minutes
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min15_nf LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min15_qfq LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min15_hfq LIKE stock_zh_a_hist_min5_nf;

-- 30 Minutes
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min30_nf LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min30_qfq LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min30_hfq LIKE stock_zh_a_hist_min5_nf;

-- 60 Minutes
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min60_nf LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min60_qfq LIKE stock_zh_a_hist_min5_nf;
-- CREATE TABLE IF NOT EXISTS stock_zh_a_hist_min60_hfq LIKE stock_zh_a_hist_min5_nf;

