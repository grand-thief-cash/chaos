-- ============================================================
-- 0005_govern_phoenixa_meta_enums.sql
-- ============================================================
-- Phase 0 of the security_registry surrogate-key refactor
-- (docs/2026-07-02 SECURITY_REGISTRY_SURROGATE_KEY_REFACTOR_INVESTIGATION.md
-- §9 阶段 0, §3.4, §10.a govern 层).
--
-- Seeds the phoenixA platform-level controlled vocabulary into
-- govern.data_enum_dictionary:
--   enum_name = asset_type / exchange / market / source
-- authored with source='phoenixa' (the platform itself), distinct from the
-- AmazingData SDK enums (source='amazing_data') seeded by 0004_govern_seed.sql.
--
-- Source-of-truth: the Go const declarations in internal/consts/.
-- Per refactor §3.3, "const 值 = enum code" — the enum `code` MUST equal the
-- corresponding const value. If a const is added/removed/renamed, update the
-- matching block here too:
--   asset_type  -> internal/consts/asset_type.go
--   exchange    -> internal/consts/exchange.go
--   market      -> internal/consts/market.go
--   source      -> internal/consts/data_source.go
--
-- Idempotent: DELETE then INSERT for source='phoenixa' at this
-- contract_version, so the migration is safe to re-run on a non-fresh DB.
--
-- NOT managed by regenerate_seed_sql.py: that script is the sole converter for
-- the AmazingData field-dictionary JSONL (scripts/field_dictionary/amazing_data/
-- *.jsonl) into 0004_govern_seed.sql, and only DELETEs source='amazing_data'.
-- The phoenixA meta-enums are a separate contract (their source-of-truth is the
-- Go consts, not an external SDK doc), so they live here as a hand-written,
-- self-contained seed.
-- ============================================================

DELETE FROM govern.data_enum_dictionary
WHERE source = 'phoenixa' AND contract_version = '2026-07-03';

INSERT INTO govern.data_enum_dictionary
    (contract_version, source, enum_name, code, label_zh, description,
     sort_order, source_doc, review_status, deprecated)
VALUES
-- asset_type  (internal/consts/asset_type.go)
('2026-07-03', 'phoenixa', 'asset_type', 'stock',   '股票',   '股票',                 1, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'asset_type', 'index',   '指数',   '指数',                 2, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'asset_type', 'etf',     'ETF',    '交易型开放式指数基金', 3, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'asset_type', 'fund',    '基金',   '公募基金',             4, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'asset_type', 'futures', '期货',   '期货',                 5, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'asset_type', 'cb',      '可转债', '可转换公司债券',       6, 'internal/consts/asset_type.go', 'platform_defined', FALSE),
-- exchange  (internal/consts/exchange.go) — global stable codes, uppercase
('2026-07-03', 'phoenixa', 'exchange', 'SH', '上海证券交易所', '上海证券交易所 (沪市)',   1, 'internal/consts/exchange.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'exchange', 'SZ', '深圳证券交易所', '深圳证券交易所 (深市)',   2, 'internal/consts/exchange.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'exchange', 'BJ', '北京证券交易所', '北京证券交易所 (北交所)', 3, 'internal/consts/exchange.go', 'platform_defined', FALSE),
-- market  (internal/consts/market.go) — business partition; zh_a ↔ SH/SZ/BJ one-to-many
('2026-07-03', 'phoenixa', 'market', 'zh_a',   'A股',  '中国大陆 A 股市场', 1, 'internal/consts/market.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'market', 'hk',     '港股', '香港市场',          2, 'internal/consts/market.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'market', 'us',     '美股', '美国市场',          3, 'internal/consts/market.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'market', 'global', '全球', '全球市场',          4, 'internal/consts/market.go', 'platform_defined', FALSE),
-- source  (internal/consts/data_source.go) — data provenance; closed set of 7
('2026-07-03', 'phoenixa', 'source', 'tushare',      'Tushare',     'Tushare 数据接口',         1, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'jqdata',       'JQData',      '聚宽 JQData 数据接口',     2, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'amazing_data', 'AmazingData', 'AmazingData 行情数据接口', 3, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'mairui',       'Mairui',      'Mairui 数据源',            4, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'akshare',      'AKShare',     'AKShare 开源金融数据接口', 5, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'baostock',     'BaoStock',    'BaoStock 证券数据接口',    6, 'internal/consts/data_source.go', 'platform_defined', FALSE),
('2026-07-03', 'phoenixa', 'source', 'csv_import',   'CSV 导入',    'CSV 文件批量导入',         7, 'internal/consts/data_source.go', 'platform_defined', FALSE);
