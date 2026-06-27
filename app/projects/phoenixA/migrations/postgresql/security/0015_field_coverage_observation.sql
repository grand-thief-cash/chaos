-- ============================================================
-- PhoenixA PostgreSQL Migration 0015: Field Coverage Observation
-- Target: chaos_db, schema: security_dev / security
-- Scope: data_field_coverage_observation
-- Storage tier: pg_default (small observability table)
-- Reason: Phase 4 #3 — observe actual data_json keys across governed
--         datasets and flag SDK-added fields the dictionary has not
--         caught up with. See design doc 2026-06-25 §11.5.
-- ============================================================

DROP TABLE IF EXISTS data_field_coverage_observation CASCADE;

CREATE TABLE data_field_coverage_observation (
    dataset       VARCHAR(64)  NOT NULL,
    source        VARCHAR(32)  NOT NULL,
    storage_table VARCHAR(64)  NOT NULL,
    observed_key  VARCHAR(128) NOT NULL,
    status        VARCHAR(16)  NOT NULL,  -- 'governed' | 'ungoverned'
    sample_count  BIGINT       NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_data_field_coverage_observation
        PRIMARY KEY (dataset, source, observed_key),
    CONSTRAINT chk_coverage_status
        CHECK (status IN ('governed', 'ungoverned'))
) TABLESPACE pg_default;

CREATE INDEX idx_coverage_status
    ON data_field_coverage_observation (status) TABLESPACE pg_default;

CREATE INDEX idx_coverage_dataset_status
    ON data_field_coverage_observation (dataset, status) TABLESPACE pg_default;

COMMENT ON TABLE data_field_coverage_observation IS
    '字段覆盖率观测表。记录每个 governed dataset 的 data_json 实际出现过的 key，与字段字典对比后标记 governed/ungoverned。ungoverned 项是 SDK 新增但字典尚未收录的字段，需治理。';
COMMENT ON COLUMN data_field_coverage_observation.dataset IS '数据集名，对应 data_dataset_dictionary.dataset。';
COMMENT ON COLUMN data_field_coverage_observation.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN data_field_coverage_observation.storage_table IS '存储表名，如 financial_statement。';
COMMENT ON COLUMN data_field_coverage_observation.observed_key IS 'data_json 中实际观测到的 key（raw_field 形态）。';
COMMENT ON COLUMN data_field_coverage_observation.status IS 'governed: 字典已收录；ungoverned: 字典未收录，待治理。';
COMMENT ON COLUMN data_field_coverage_observation.sample_count IS '本次扫描中该 key 出现的行数（采样行内的计数）。';
COMMENT ON COLUMN data_field_coverage_observation.first_seen_at IS '该 key 首次被观测到的时间。';
COMMENT ON COLUMN data_field_coverage_observation.last_seen_at IS '该 key 最近被观测到的时间。';
