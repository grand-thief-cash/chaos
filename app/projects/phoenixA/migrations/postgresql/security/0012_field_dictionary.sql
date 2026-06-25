-- ============================================================
-- PhoenixA PostgreSQL Migration 0012: Data Field Dictionary
-- Target: chaos_db, schema: security_dev / security
-- Scope: data_dataset_dictionary, data_field_dictionary,
--        data_enum_dictionary
--
-- Storage tier:
--   - dictionary tables -> pg_default (NVMe metadata)
--   - source business data remains on warm_storage
--
-- This migration intentionally recreates the dictionary tables. The field
-- contract is generated from versioned source files under
-- config/field_dictionary/, so historical dictionary rows do not need to be
-- preserved during early PhoenixA schema stabilization.
-- ============================================================

DROP VIEW IF EXISTS v_data_field_dictionary_active;
DROP TABLE IF EXISTS data_field_dictionary CASCADE;
DROP TABLE IF EXISTS data_enum_dictionary CASCADE;
DROP TABLE IF EXISTS data_dataset_dictionary CASCADE;

CREATE TABLE data_dataset_dictionary (
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

CREATE INDEX idx_data_dataset_dict_source
    ON data_dataset_dictionary (source, dataset) TABLESPACE pg_default;

CREATE TABLE data_field_dictionary (
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

CREATE INDEX idx_data_field_dict_lookup
    ON data_field_dictionary (source, dataset, data_type, raw_field) TABLESPACE pg_default;

CREATE INDEX idx_data_field_dict_canonical
    ON data_field_dictionary (source, dataset, data_type, canonical_field) TABLESPACE pg_default;

CREATE INDEX idx_data_field_dict_core
    ON data_field_dictionary (source, dataset, data_type, is_core)
    TABLESPACE pg_default
    WHERE is_core = TRUE AND deprecated = FALSE;

CREATE INDEX idx_data_field_dict_enum_ref
    ON data_field_dictionary (source, enum_ref)
    TABLESPACE pg_default
    WHERE enum_ref != '';

CREATE INDEX idx_data_field_dict_aliases_gin
    ON data_field_dictionary USING GIN (aliases jsonb_path_ops) TABLESPACE pg_default;

CREATE TABLE data_enum_dictionary (
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

CREATE INDEX idx_data_enum_dict_lookup
    ON data_enum_dictionary (source, enum_name, sort_order, code) TABLESPACE pg_default;

CREATE VIEW v_data_field_dictionary_active AS
SELECT *
FROM data_field_dictionary
WHERE deprecated = FALSE;

COMMENT ON TABLE data_dataset_dictionary IS '数据集字典。描述 PhoenixA 对外可发现的数据集、类型列表、底层表和存储层级。';
COMMENT ON COLUMN data_dataset_dictionary.id IS '自增主键。';
COMMENT ON COLUMN data_dataset_dictionary.contract_version IS '字段契约版本。用于区分不同批次的 SDK 字段整理结果。';
COMMENT ON COLUMN data_dataset_dictionary.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN data_dataset_dictionary.dataset IS 'PhoenixA 数据集标识，如 financial_statement、corporate_action、equity_structure。';
COMMENT ON COLUMN data_dataset_dictionary.label_zh IS '数据集中文名称。';
COMMENT ON COLUMN data_dataset_dictionary.data_types IS '该数据集包含的数据类型 JSON 数组，如 balance_sheet、income、cashflow。';
COMMENT ON COLUMN data_dataset_dictionary.storage_table IS '该数据集对应的业务明细存储表。';
COMMENT ON COLUMN data_dataset_dictionary.storage_tablespace IS '业务明细表所在 tablespace，如 warm_storage。';
COMMENT ON COLUMN data_dataset_dictionary.dictionary_tablespace IS '字典元数据所在 tablespace，当前为 pg_default。';
COMMENT ON COLUMN data_dataset_dictionary.source_doc IS '字段来源文档或 SDK 章节。';
COMMENT ON COLUMN data_dataset_dictionary.created_at IS '记录创建时间。';
COMMENT ON COLUMN data_dataset_dictionary.updated_at IS '记录更新时间。';

COMMENT ON TABLE data_field_dictionary IS '字段字典。PhoenixA 对外字段发现、字段含义解释、字段投影校验和 JSONB 字段解析的权威机器可读契约。';
COMMENT ON COLUMN data_field_dictionary.id IS '自增主键。';
COMMENT ON COLUMN data_field_dictionary.contract_version IS '字段契约版本。和源文件 config/field_dictionary 中的 contract_version 对齐。';
COMMENT ON COLUMN data_field_dictionary.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN data_field_dictionary.dataset IS 'PhoenixA 数据集标识，如 financial_statement、corporate_action、equity_structure。';
COMMENT ON COLUMN data_field_dictionary.data_type IS '数据集内类型，如 balance_sheet、income、cashflow、dividend、right_issue。';
COMMENT ON COLUMN data_field_dictionary.data_type_label_zh IS '数据类型中文名称。';
COMMENT ON COLUMN data_field_dictionary.sdk_section IS 'AmazingData SDK 文档章节号。';
COMMENT ON COLUMN data_field_dictionary.sdk_function IS 'AmazingData SDK 函数名，如 get_balance_sheet。';
COMMENT ON COLUMN data_field_dictionary.raw_field IS 'SDK 原始字段名，保留大写格式，如 TOTAL_ASSETS。';
COMMENT ON COLUMN data_field_dictionary.canonical_field IS 'PhoenixA 推荐标准字段名，通常为 snake_case；顶层字段映射为表字段名。';
COMMENT ON COLUMN data_field_dictionary.label_zh IS '字段中文名称。';
COMMENT ON COLUMN data_field_dictionary.description IS '字段说明、业务口径或备注。';
COMMENT ON COLUMN data_field_dictionary.value_type IS 'PhoenixA 规范类型：number、integer、string、date、enum、boolean。';
COMMENT ON COLUMN data_field_dictionary.source_value_type IS 'SDK 文档中的原始类型，用于保留来源差异和校对线索。';
COMMENT ON COLUMN data_field_dictionary.unit IS '原始字段单位，如 元、股、万股、元/股、%。';
COMMENT ON COLUMN data_field_dictionary.scale IS '单位换算因子。例：万股转股时为 10000；不需要换算时为空。';
COMMENT ON COLUMN data_field_dictionary.enum_ref IS '枚举字典引用，如 REPORT_TYPE、STATEMENT_TYPE、DIV_PROGRESS。';
COMMENT ON COLUMN data_field_dictionary.storage_location IS '字段落点：top_level 表示稳定顶层列；data_json 表示存储在 JSONB 明细字段中。';
COMMENT ON COLUMN data_field_dictionary.is_metadata IS '是否为元数据字段。元数据字段通常来自 SDK payload 但落为顶层列。';
COMMENT ON COLUMN data_field_dictionary.is_core IS '是否为高频核心字段。外部服务默认字段集和核心视图可优先使用。';
COMMENT ON COLUMN data_field_dictionary.comp_type_scope IS '适用公司类型范围，如 all、non_financial、bank、insurance、securities。';
COMMENT ON COLUMN data_field_dictionary.aliases IS '字段别名 JSON 数组。用于兼容 SDK 文档断行、历史字段名或同义字段。';
COMMENT ON COLUMN data_field_dictionary.source_doc IS '字段来源说明，如 AmazingData 3.5.5.1 get_balance_sheet。';
COMMENT ON COLUMN data_field_dictionary.source_path IS '字段来源文件路径，仓库内相对路径。';
COMMENT ON COLUMN data_field_dictionary.review_status IS '字段整理状态，如 bootstrap、manual checked、SDK checked。';
COMMENT ON COLUMN data_field_dictionary.deprecated IS '字段是否废弃。废弃字段保留用于兼容和迁移提示。';
COMMENT ON COLUMN data_field_dictionary.created_at IS '记录创建时间。';
COMMENT ON COLUMN data_field_dictionary.updated_at IS '记录更新时间。';

COMMENT ON TABLE data_enum_dictionary IS '枚举字典。保存 SDK 枚举代码和中文含义，供字段发现、查询参数校验和响应解释使用。';
COMMENT ON COLUMN data_enum_dictionary.id IS '自增主键。';
COMMENT ON COLUMN data_enum_dictionary.contract_version IS '字段契约版本。';
COMMENT ON COLUMN data_enum_dictionary.source IS '数据源标识，如 amazing_data。';
COMMENT ON COLUMN data_enum_dictionary.enum_name IS '枚举名称，如 REPORT_TYPE、STATEMENT_TYPE、DIV_PROGRESS。';
COMMENT ON COLUMN data_enum_dictionary.code IS '枚举代码，统一按字符串存储。';
COMMENT ON COLUMN data_enum_dictionary.label_zh IS '枚举值中文名称。';
COMMENT ON COLUMN data_enum_dictionary.description IS '枚举值说明。';
COMMENT ON COLUMN data_enum_dictionary.sort_order IS '枚举展示和排序顺序。';
COMMENT ON COLUMN data_enum_dictionary.source_doc IS '枚举来源 SDK 章节或字段备注。';
COMMENT ON COLUMN data_enum_dictionary.review_status IS '枚举整理状态。';
COMMENT ON COLUMN data_enum_dictionary.deprecated IS '枚举值是否废弃。';
COMMENT ON COLUMN data_enum_dictionary.created_at IS '记录创建时间。';
COMMENT ON COLUMN data_enum_dictionary.updated_at IS '记录更新时间。';

COMMENT ON VIEW v_data_field_dictionary_active IS '未废弃字段的便捷视图，用于字段发现 API 和查询校验。';
