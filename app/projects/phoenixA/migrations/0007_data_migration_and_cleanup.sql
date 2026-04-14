-- ============================================================
-- PhoenixA v2 数据迁移 & 旧表清理脚本
-- 执行前提：0005_v2_architecture.sql 已执行（新表已创建）
-- 执行顺序：先迁移数据，验证后再清理旧表
-- ============================================================

-- ======================== STEP 1: 迁移数据 ========================

-- 1.1 stock_zh_a_list → security_registry
INSERT IGNORE INTO security_registry (symbol, asset_type, market, exchange, name)
SELECT code, 'stock', 'zh_a', exchange, company
FROM stock_zh_a_list;

SELECT CONCAT('security_registry migrated: ', COUNT(*), ' rows') AS info FROM security_registry;

-- 1.2 stock_zh_a_hist_daily_nf → bars_stock_zh_a_daily_nf (标准列)
INSERT IGNORE INTO bars_stock_zh_a_daily_nf (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg)
SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg
FROM stock_zh_a_hist_daily_nf;

SELECT CONCAT('bars_stock_zh_a_daily_nf migrated: ', COUNT(*), ' rows') AS info FROM bars_stock_zh_a_daily_nf;

-- 1.3 stock_zh_a_hist_daily_nf → bars_ext_baostock_stock_zh_a_daily (扩展列，仅有值的行)
INSERT IGNORE INTO bars_ext_baostock_stock_zh_a_daily (symbol, trade_date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm)
SELECT code, date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm
FROM stock_zh_a_hist_daily_nf
WHERE (turn IS NOT NULL AND turn != 0)
   OR (pe_ttm IS NOT NULL AND pe_ttm != 0)
   OR (ps_ttm IS NOT NULL AND ps_ttm != 0)
   OR (pb_mrq IS NOT NULL AND pb_mrq != 0)
   OR (pcf_ncf_ttm IS NOT NULL AND pcf_ncf_ttm != 0);

SELECT CONCAT('bars_ext_baostock_stock_zh_a_daily migrated: ', COUNT(*), ' rows') AS info FROM bars_ext_baostock_stock_zh_a_daily;

-- 1.4 stock_zh_a_hist_daily_hfq → bars_stock_zh_a_daily_hfq
INSERT IGNORE INTO bars_stock_zh_a_daily_hfq (symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg)
SELECT code, date, open, high, low, close, volume, amount, preclose, pct_chg
FROM stock_zh_a_hist_daily_hfq;

SELECT CONCAT('bars_stock_zh_a_daily_hfq migrated: ', COUNT(*), ' rows') AS info FROM bars_stock_zh_a_daily_hfq;

-- 1.5 mkt_category_mairui → taxonomy_category
INSERT IGNORE INTO taxonomy_category (source, code, name, parent_code, level, is_leaf, attrs_json)
SELECT 'mairui', code, name, parent_code, level, is_leaf,
       JSON_OBJECT('parent_name', parent_name, 'type1', type1, 'type2', type2)
FROM mkt_category_mairui;

SELECT CONCAT('taxonomy_category (mairui) migrated: ', COUNT(*), ' rows') AS info
FROM taxonomy_category WHERE source = 'mairui';

-- 1.6 category_stock_map → taxonomy_security_map
INSERT IGNORE INTO taxonomy_security_map (source, category_code, symbol, asset_type, market)
SELECT 'mairui', category_code, stock_code, 'stock', 'zh_a'
FROM category_stock_map;

SELECT CONCAT('taxonomy_security_map migrated: ', COUNT(*), ' rows') AS info FROM taxonomy_security_map;


-- ======================== STEP 2: 数据校验 ========================
-- 执行这些查询确认迁移数据正确，然后才执行 STEP 3

-- 对比 stock_zh_a_list vs security_registry
SELECT
    (SELECT COUNT(*) FROM stock_zh_a_list) AS old_count,
    (SELECT COUNT(*) FROM security_registry WHERE asset_type='stock' AND market='zh_a') AS new_count;

-- 对比 stock_zh_a_hist_daily_nf vs bars_stock_zh_a_daily_nf
SELECT
    (SELECT COUNT(*) FROM stock_zh_a_hist_daily_nf) AS old_count,
    (SELECT COUNT(*) FROM bars_stock_zh_a_daily_nf) AS new_count;

-- 对比 mkt_category_mairui vs taxonomy_category
SELECT
    (SELECT COUNT(*) FROM mkt_category_mairui) AS old_count,
    (SELECT COUNT(*) FROM taxonomy_category WHERE source='mairui') AS new_count;

-- 对比 category_stock_map vs taxonomy_security_map
SELECT
    (SELECT COUNT(*) FROM category_stock_map) AS old_count,
    (SELECT COUNT(*) FROM taxonomy_security_map) AS new_count;


-- ======================== STEP 3: 清理旧表（验证通过后执行）========================
-- ⚠️ 确认 STEP 2 的 old_count == new_count 后再执行以下语句！

-- 旧表重命名为 _archive（保留一段时间，确认没问题后再 DROP）
RENAME TABLE stock_zh_a_list TO stock_zh_a_list_archive;
RENAME TABLE stock_zh_a_hist_daily_nf TO stock_zh_a_hist_daily_nf_archive;
RENAME TABLE stock_zh_a_hist_daily_hfq TO stock_zh_a_hist_daily_hfq_archive;
RENAME TABLE mkt_category_mairui TO mkt_category_mairui_archive;
RENAME TABLE category_stock_map TO category_stock_map_archive;

-- 如果有 mkt_category_swhy 表也归档
-- RENAME TABLE mkt_category_swhy TO mkt_category_swhy_archive;


-- ======================== STEP 4: 最终清理（归档表确认不再需要后）========================
-- DROP TABLE IF EXISTS stock_zh_a_list_archive;
-- DROP TABLE IF EXISTS stock_zh_a_hist_daily_nf_archive;
-- DROP TABLE IF EXISTS stock_zh_a_hist_daily_hfq_archive;
-- DROP TABLE IF EXISTS mkt_category_mairui_archive;
-- DROP TABLE IF EXISTS category_stock_map_archive;
-- DROP TABLE IF EXISTS mkt_category_swhy_archive;

