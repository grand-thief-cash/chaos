-- ============================================================
-- PhoenixA PostgreSQL Migration 0003: Govern layer (PhoenixA-owned governance / metadata)
-- Layer: govern
-- Scope: data_dataset_dictionary, data_field_dictionary, data_enum_dictionary,
--        data_field_coverage_observation
--
-- Govern = PhoenixA-owned governance / observability metadata. External-source
-- landing tables (including the security_registry master) live in ods.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - dictionary tables / data_field_coverage_observation -> pg_default (NVMe, metadata)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS govern;

-- ──────────────────────────────────────────────────────────
-- 1. data_dataset_dictionary
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS govern.data_dataset_dictionary (
    id                    BIGSERIAL      PRIMARY KEY,
    contract_version      VARCHAR(32)    NOT NULL,
    source                VARCHAR(32)    NOT NULL,
    dataset               VARCHAR(64)    NOT NULL,
    label_zh              VARCHAR(128)   NOT NULL DEFAULT '',
    data_types            JSONB          NOT NULL DEFAULT '[]'::jsonb,
    storage_table         VARCHAR(128)   NOT NULL DEFAULT '',
    storage_tablespace    VARCHAR(64)    NOT NULL DEFAULT '',
    dictionary_tablespace VARCHAR(64)    NOT NULL DEFAULT 'pg_default',
    source_doc            VARCHAR(256)   NOT NULL DEFAULT '',
    created_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_data_dataset_dict UNIQUE (source, dataset, contract_version)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_data_dataset_dict_source
    ON govern.data_dataset_dictionary (source, dataset) TABLESPACE pg_default;

-- ──────────────────────────────────────────────────────────
-- 2. data_field_dictionary
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS govern.data_field_dictionary (
    id                 BIGSERIAL      PRIMARY KEY,
    contract_version   VARCHAR(32)    NOT NULL,
    source             VARCHAR(32)    NOT NULL,
    dataset            VARCHAR(64)    NOT NULL,
    data_type          VARCHAR(64)    NOT NULL,
    data_type_label_zh VARCHAR(128)   NOT NULL DEFAULT '',
    sdk_section        VARCHAR(32)    NOT NULL DEFAULT '',
    sdk_function       VARCHAR(64)    NOT NULL DEFAULT '',
    raw_field          VARCHAR(128)   NOT NULL,
    canonical_field    VARCHAR(128)   NOT NULL,
    label_zh           VARCHAR(256)   NOT NULL DEFAULT '',
    description        TEXT           NOT NULL DEFAULT '',
    value_type         VARCHAR(32)    NOT NULL,
    source_value_type  VARCHAR(32)    NOT NULL DEFAULT '',
    unit               VARCHAR(64)    NOT NULL DEFAULT '',
    scale              NUMERIC(32,12),
    enum_ref           VARCHAR(64)    NOT NULL DEFAULT '',
    storage_location   VARCHAR(32)    NOT NULL,
    is_metadata        BOOLEAN        NOT NULL DEFAULT FALSE,
    is_core            BOOLEAN        NOT NULL DEFAULT FALSE,
    comp_type_scope    VARCHAR(64)    NOT NULL DEFAULT 'all',
    aliases            JSONB          NOT NULL DEFAULT '[]'::jsonb,
    source_doc         VARCHAR(256)   NOT NULL DEFAULT '',
    source_path        VARCHAR(512)   NOT NULL DEFAULT '',
    review_status      VARCHAR(96)    NOT NULL DEFAULT '',
    deprecated         BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_data_field_dict UNIQUE (source, dataset, data_type, raw_field, contract_version),
    CONSTRAINT chk_data_field_value_type
        CHECK (value_type IN ('number', 'integer', 'string', 'date', 'enum', 'boolean')),
    CONSTRAINT chk_data_field_storage_location
        CHECK (storage_location IN ('top_level', 'data_json'))
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_data_field_dict_lookup
    ON govern.data_field_dictionary (source, dataset, data_type, raw_field) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_data_field_dict_canonical
    ON govern.data_field_dictionary (source, dataset, data_type, canonical_field) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_data_field_dict_core
    ON govern.data_field_dictionary (source, dataset, data_type, is_core)
    TABLESPACE pg_default
    WHERE is_core = TRUE AND deprecated = FALSE;
CREATE INDEX IF NOT EXISTS idx_data_field_dict_enum_ref
    ON govern.data_field_dictionary (source, enum_ref)
    TABLESPACE pg_default
    WHERE enum_ref != '';
CREATE INDEX IF NOT EXISTS idx_data_field_dict_aliases_gin
    ON govern.data_field_dictionary USING GIN (aliases jsonb_path_ops) TABLESPACE pg_default;

-- ──────────────────────────────────────────────────────────
-- 3. data_enum_dictionary
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS govern.data_enum_dictionary (
    id               BIGSERIAL      PRIMARY KEY,
    contract_version VARCHAR(32)    NOT NULL,
    source           VARCHAR(32)    NOT NULL,
    enum_name        VARCHAR(64)    NOT NULL,
    code             VARCHAR(32)    NOT NULL,
    label_zh         VARCHAR(256)   NOT NULL,
    description      TEXT           NOT NULL DEFAULT '',
    sort_order       INT            NOT NULL DEFAULT 0,
    source_doc       VARCHAR(256)   NOT NULL DEFAULT '',
    review_status    VARCHAR(96)    NOT NULL DEFAULT '',
    deprecated       BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_data_enum_dict UNIQUE (source, enum_name, code, contract_version)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_data_enum_dict_lookup
    ON govern.data_enum_dictionary (source, enum_name, sort_order, code) TABLESPACE pg_default;

CREATE OR REPLACE VIEW govern.v_data_field_dictionary_active AS
SELECT *
FROM govern.data_field_dictionary
WHERE deprecated = FALSE;

-- ──────────────────────────────────────────────────────────
-- 4. data_field_coverage_observation
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS govern.data_field_coverage_observation (
    dataset       VARCHAR(64)  NOT NULL,
    source        VARCHAR(32)  NOT NULL,
    storage_table VARCHAR(64)  NOT NULL,
    observed_key  VARCHAR(128) NOT NULL,
    status        VARCHAR(16)  NOT NULL,
    sample_count  BIGINT       NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_data_field_coverage_observation
        PRIMARY KEY (dataset, source, observed_key),
    CONSTRAINT chk_coverage_status
        CHECK (status IN ('governed', 'ungoverned'))
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_coverage_status
    ON govern.data_field_coverage_observation (status) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_coverage_dataset_status
    ON govern.data_field_coverage_observation (dataset, status) TABLESPACE pg_default;

COMMENT ON TABLE govern.data_field_coverage_observation IS
    '字段覆盖率观测表。记录每个 governed dataset 的 data_json 实际出现过的 key，与字段字典对比后标记 governed/ungoverned。ungoverned 项是 SDK 新增但字典尚未收录的字段，需治理。';
COMMENT ON COLUMN govern.data_field_coverage_observation.dataset IS '数据集名，对应 govern.data_dataset_dictionary.dataset。';
COMMENT ON COLUMN govern.data_field_coverage_observation.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN govern.data_field_coverage_observation.storage_table IS '存储表名，如 financial_statement。';
COMMENT ON COLUMN govern.data_field_coverage_observation.observed_key IS 'data_json 中实际观测到的 key（raw_field 形态）。';
COMMENT ON COLUMN govern.data_field_coverage_observation.status IS 'governed: 字典已收录；ungoverned: 字典未收录，待治理。';
COMMENT ON COLUMN govern.data_field_coverage_observation.sample_count IS '本次扫描中该 key 出现的行数（采样行内的计数）。';
COMMENT ON COLUMN govern.data_field_coverage_observation.first_seen_at IS '该 key 首次被观测到的时间。';
COMMENT ON COLUMN govern.data_field_coverage_observation.last_seen_at IS '该 key 最近被观测到的时间。';
