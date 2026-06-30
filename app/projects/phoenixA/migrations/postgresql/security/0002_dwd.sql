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
