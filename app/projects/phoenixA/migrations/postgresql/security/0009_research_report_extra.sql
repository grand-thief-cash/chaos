-- ──────────────────────────────────────────────────────────
-- research_report_download_record.extra
--
-- Adds a JSONB `extra` column to ods.research_report_download_record for
-- Eastmoney research-report business fields the user wants preserved alongside
-- the download-state tracker: rating, rating change, last-month report count,
-- current/next-year EPS & PE predictions, industry, researcher, stock name.
-- These are NOT download-state; they are report-content metadata that Eastmoney
-- returns in the list payload and are convenient to capture at list time.
--
-- Stored as a JSONB object (CHECK jsonb_typeof='object') so it is queryable by
-- key (extra->'em_rating_name'). Mirrors the data_json convention used by
-- corporate_action / equity_structure.
-- ──────────────────────────────────────────────────────────
ALTER TABLE ods.research_report_download_record
    ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE ods.research_report_download_record
    DROP CONSTRAINT IF EXISTS chk_rrdlrec_extra;
ALTER TABLE ods.research_report_download_record
    ADD CONSTRAINT chk_rrdlrec_extra CHECK (jsonb_typeof(extra) = 'object');

COMMENT ON COLUMN ods.research_report_download_record.extra IS '研报业务元数据 JSONB（东方财富列表页字段）。存 object，可按 key 查询。包含：em_rating_name（东财评级）、last_em_rating_name（上次评级）、rating_change（评级变动编码）、rating_change_name（评级变动名称）、report_count_1m（近一月个股研报数）、predict_this_year_eps/pe（当年盈利预测）、predict_next_year_eps/pe（次年盈利预测）、industry_code/name（行业）、researcher（研究员）、stock_name（股票名称）。artemis 在 LIST 阶段 upsert 时写入；ON CONFLICT 会刷新。';
