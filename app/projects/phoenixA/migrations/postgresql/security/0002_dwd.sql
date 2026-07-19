-- ============================================================
-- PhoenixA PostgreSQL Migration 0002: DWD layer (derived / processed)
-- Layer: dwd
-- Scope: taxonomy_category_derived_flags
--
-- Stores PhoenixA-owned semantic derivations (derived_flags) outside
-- the ODS taxonomy_category table so raw taxonomy categories remain
-- source-faithful while downstream APIs still expose canonical flags.
--
-- Storage tier: pg_default (NVMe, small metadata)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS dwd;

CREATE TABLE IF NOT EXISTS dwd.taxonomy_category_derived_flags (
    id             BIGSERIAL    PRIMARY KEY,
    source         VARCHAR(32)  NOT NULL,
    taxonomy       VARCHAR(32)  NOT NULL,
    market         VARCHAR(16)  NOT NULL DEFAULT 'zh_a',
    code           VARCHAR(64)  NOT NULL,
    derived_flags  JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_tcdf_src_tax_mkt_code UNIQUE (source, taxonomy, market, code)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_tcdf_lookup
    ON dwd.taxonomy_category_derived_flags (source, taxonomy, market, code);

CREATE INDEX IF NOT EXISTS idx_tcdf_flags_gin
    ON dwd.taxonomy_category_derived_flags USING GIN (derived_flags jsonb_path_ops);

COMMENT ON TABLE dwd.taxonomy_category_derived_flags IS 'PhoenixA 派生的行业分类语义标记（DWD 加工层）。不来自外部 SDK，由 DAO 层基于 ODS taxonomy_category 计算（taxonomy_dao.go deriveCategoryFlags / upsertDerivedFlagsForCategories），在 BatchUpsertCategories 写入 ODS 后增量刷新。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.id IS '自增主键。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.source IS '数据源标识，复制自 ODS taxonomy_category.source（如 amazing_data）。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.taxonomy IS '分类体系标识，复制自 ODS taxonomy_category.taxonomy（如 swhy）。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.market IS '市场标识，默认 zh_a，复制自 ODS taxonomy_category.market。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.code IS '分类节点代码，复制自 ODS taxonomy_category.code。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.derived_flags IS 'PhoenixA 派生语义标记 JSONB。当前已知标记：financial_sector（bool，是否金融板块，由 isFinancialSectorCategory 沿父节点链按名称关键词[银行/保险/证券/多元金融/非银金融/金融]及申万代码判断）；另从 attrs_json 解析 derived_flags 子对象与 is_financial_sector 字段。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.created_at IS '记录创建时间。';
COMMENT ON COLUMN dwd.taxonomy_category_derived_flags.updated_at IS '记录更新时间。';
