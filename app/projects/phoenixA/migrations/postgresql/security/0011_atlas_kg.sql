CREATE SCHEMA IF NOT EXISTS atlas_kg;

CREATE TABLE IF NOT EXISTS atlas_kg.extraction_run (
    id UUID PRIMARY KEY,
    source_document_id VARCHAR(160) NOT NULL,
    source_report_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    result JSONB NULL CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_atlas_extraction_source ON atlas_kg.extraction_run(source_document_id);
CREATE INDEX IF NOT EXISTS idx_atlas_extraction_status ON atlas_kg.extraction_run(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS atlas_kg.governance_record (
    id UUID PRIMARY KEY,
    kind VARCHAR(32) NOT NULL CHECK (kind IN ('discovery', 'semantic-version', 'crosswalk')),
    version VARCHAR(80) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_atlas_governance_version
    ON atlas_kg.governance_record(kind, version) WHERE version <> '';

CREATE TABLE IF NOT EXISTS atlas_kg.knowledge_entity (
    id UUID PRIMARY KEY,
    canonical_name VARCHAR(512) NOT NULL,
    normalized_name VARCHAR(512) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    country_code VARCHAR(16) NOT NULL DEFAULT '',
    resolution_state VARCHAR(32) NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_atlas_entity_name ON atlas_kg.knowledge_entity(normalized_name);
CREATE INDEX IF NOT EXISTS idx_atlas_entity_type ON atlas_kg.knowledge_entity(entity_type);

CREATE TABLE IF NOT EXISTS atlas_kg.entity_alias (
    id BIGSERIAL PRIMARY KEY,
    entity_id UUID NOT NULL REFERENCES atlas_kg.knowledge_entity(id) ON DELETE CASCADE,
    alias VARCHAR(512) NOT NULL,
    normalized_alias VARCHAR(512) NOT NULL,
    language VARCHAR(16) NOT NULL DEFAULT '',
    source VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(entity_id, normalized_alias)
);
CREATE INDEX IF NOT EXISTS idx_atlas_alias_normalized ON atlas_kg.entity_alias(normalized_alias);

CREATE TABLE IF NOT EXISTS atlas_kg.security_entity_link (
    entity_id UUID PRIMARY KEY REFERENCES atlas_kg.knowledge_entity(id) ON DELETE CASCADE,
    security_id BIGINT NOT NULL REFERENCES ods.security_registry(id),
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    resolution_method VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(security_id)
);

CREATE TABLE IF NOT EXISTS atlas_kg.claim (
    id UUID PRIMARY KEY,
    claim_type VARCHAR(32) NOT NULL CHECK (claim_type IN ('RELATION', 'QUANTIFIED', 'ANALYST_VIEW')),
    source_document_id VARCHAR(160) NOT NULL,
    subject_entity_id UUID NULL REFERENCES atlas_kg.knowledge_entity(id),
    object_entity_id UUID NULL REFERENCES atlas_kg.knowledge_entity(id),
    canonical_predicate VARCHAR(128) NOT NULL DEFAULT '',
    assertion_type VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_atlas_claim_subject ON atlas_kg.claim(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_atlas_claim_object ON atlas_kg.claim(object_entity_id);
CREATE INDEX IF NOT EXISTS idx_atlas_claim_predicate ON atlas_kg.claim(canonical_predicate);
CREATE INDEX IF NOT EXISTS idx_atlas_claim_document ON atlas_kg.claim(source_document_id);
