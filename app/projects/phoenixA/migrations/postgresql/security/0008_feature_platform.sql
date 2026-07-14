-- ============================================================
-- PhoenixA PostgreSQL Migration 0008: Feature Platform control plane
-- Layer: govern + dwd
-- Scope: immutable feature registry, dependency graph, runs/backfills,
--        subject snapshots, run items, and numeric feature values.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS govern;
CREATE SCHEMA IF NOT EXISTS dwd;

CREATE TABLE IF NOT EXISTS govern.feature_definition (
    id              BIGSERIAL PRIMARY KEY,
    feature_code    VARCHAR(160) NOT NULL UNIQUE,
    display_name    VARCHAR(256) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    kind            VARCHAR(32) NOT NULL,
    entity_type     VARCHAR(32) NOT NULL,
    value_type      VARCHAR(32) NOT NULL,
    unit            VARCHAR(64) NOT NULL DEFAULT '',
    category        VARCHAR(64) NOT NULL DEFAULT '',
    owner           VARCHAR(128) NOT NULL DEFAULT '',
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_feature_definition_kind
        CHECK (kind IN ('raw','metric','factor','signal','prediction','label')),
    CONSTRAINT chk_feature_definition_entity_type
        CHECK (entity_type = 'security'),
    CONSTRAINT chk_feature_definition_value_type
        CHECK (value_type IN ('number','integer','boolean','enum','string','json','vector','distribution')),
    CONSTRAINT chk_feature_definition_status
        CHECK (status IN ('draft','active','deprecated','retired')),
    CONSTRAINT chk_feature_definition_tags
        CHECK (jsonb_typeof(tags) = 'array')
) TABLESPACE pg_default;

CREATE TABLE IF NOT EXISTS govern.feature_version (
    id                  BIGSERIAL PRIMARY KEY,
    feature_id          BIGINT NOT NULL REFERENCES govern.feature_definition(id),
    version_number      INTEGER NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'draft',
    frequency           VARCHAR(32) NOT NULL DEFAULT 'on_demand',
    as_of_semantics     VARCHAR(32) NOT NULL DEFAULT 'snapshot',
    missing_policy      VARCHAR(32) NOT NULL DEFAULT 'explicit_missing',
    manifest_checksum   CHAR(64) NOT NULL,
    manifest_snapshot   JSONB NOT NULL,
    published_at        TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_feature_version UNIQUE (feature_id, version_number),
    CONSTRAINT chk_feature_version_number CHECK (version_number > 0),
    CONSTRAINT chk_feature_version_status
        CHECK (status IN ('draft','published','deprecated','retired')),
    CONSTRAINT chk_feature_version_manifest
        CHECK (jsonb_typeof(manifest_snapshot) = 'object')
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_feature_version_status
    ON govern.feature_version (status, feature_id, version_number DESC);

CREATE TABLE IF NOT EXISTS govern.feature_implementation (
    id                       BIGSERIAL PRIMARY KEY,
    feature_version_id       BIGINT NOT NULL REFERENCES govern.feature_version(id),
    kind                     VARCHAR(32) NOT NULL,
    producer_service         VARCHAR(64) NOT NULL,
    backend                  VARCHAR(64) NOT NULL DEFAULT '',
    entrypoint               VARCHAR(512) NOT NULL DEFAULT '',
    implementation_revision  INTEGER NOT NULL DEFAULT 1,
    config                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum                 CHAR(64) NOT NULL,
    is_canonical             BOOLEAN NOT NULL DEFAULT TRUE,
    status                   VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_feature_impl_revision
        UNIQUE (feature_version_id, producer_service, backend, implementation_revision),
    CONSTRAINT chk_feature_impl_revision CHECK (implementation_revision > 0),
    CONSTRAINT chk_feature_impl_kind
        CHECK (kind IN ('python','expression','vendor','model','llm','external')),
    CONSTRAINT chk_feature_impl_status
        CHECK (status IN ('draft','active','disabled')),
    CONSTRAINT chk_feature_impl_config
        CHECK (jsonb_typeof(config) = 'object')
) TABLESPACE pg_default;

CREATE UNIQUE INDEX IF NOT EXISTS uk_feature_impl_canonical
    ON govern.feature_implementation (feature_version_id)
    WHERE is_canonical = TRUE AND status = 'active';

CREATE TABLE IF NOT EXISTS govern.feature_dependency (
    id                              BIGSERIAL PRIMARY KEY,
    feature_version_id              BIGINT NOT NULL REFERENCES govern.feature_version(id),
    dependency_kind                 VARCHAR(32) NOT NULL,
    depends_on_feature_version_id   BIGINT REFERENCES govern.feature_version(id),
    data_field_dictionary_id        BIGINT REFERENCES govern.data_field_dictionary(id),
    dependency_ref_snapshot         JSONB NOT NULL,
    ordinal                         INTEGER NOT NULL DEFAULT 0,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_feature_dependency_kind
        CHECK (dependency_kind IN ('feature','data_field')),
    CONSTRAINT chk_feature_dependency_target CHECK (
        (dependency_kind = 'feature'
         AND depends_on_feature_version_id IS NOT NULL
         AND data_field_dictionary_id IS NULL)
        OR
        (dependency_kind = 'data_field'
         AND depends_on_feature_version_id IS NULL
         AND data_field_dictionary_id IS NOT NULL)
    ),
    CONSTRAINT chk_feature_dependency_not_self
        CHECK (feature_version_id IS DISTINCT FROM depends_on_feature_version_id),
    CONSTRAINT chk_feature_dependency_snapshot
        CHECK (jsonb_typeof(dependency_ref_snapshot) = 'object')
) TABLESPACE pg_default;

CREATE UNIQUE INDEX IF NOT EXISTS uk_feature_dependency_feature
    ON govern.feature_dependency (feature_version_id, depends_on_feature_version_id)
    WHERE dependency_kind = 'feature';

CREATE UNIQUE INDEX IF NOT EXISTS uk_feature_dependency_field
    ON govern.feature_dependency (feature_version_id, data_field_dictionary_id)
    WHERE dependency_kind = 'data_field';

CREATE INDEX IF NOT EXISTS idx_feature_dependency_upstream
    ON govern.feature_dependency (depends_on_feature_version_id)
    WHERE dependency_kind = 'feature';

CREATE TABLE IF NOT EXISTS govern.feature_backfill_job (
    backfill_id               UUID PRIMARY KEY,
    root_feature_version_ids  BIGINT[] NOT NULL,
    start_as_of               TIMESTAMPTZ NOT NULL,
    end_as_of                 TIMESTAMPTZ NOT NULL,
    step                      VARCHAR(32) NOT NULL,
    calendar_code             VARCHAR(64) NOT NULL DEFAULT '',
    expanded_as_of_times      JSONB NOT NULL,
    data_cutoff_policy        JSONB NOT NULL,
    source_profile            VARCHAR(64) NOT NULL DEFAULT 'default',
    market                    VARCHAR(32) NOT NULL DEFAULT '',
    universe_request          JSONB NOT NULL,
    max_concurrency           INTEGER NOT NULL DEFAULT 1,
    status                    VARCHAR(32) NOT NULL,
    total_count               INTEGER NOT NULL DEFAULT 0,
    succeeded_count           INTEGER NOT NULL DEFAULT 0,
    failed_count              INTEGER NOT NULL DEFAULT 0,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_feature_backfill_range CHECK (start_as_of <= end_as_of),
    CONSTRAINT chk_feature_backfill_roots CHECK (cardinality(root_feature_version_ids) > 0),
    CONSTRAINT chk_feature_backfill_step
        CHECK (step IN ('daily','weekly','monthly','quarterly','explicit')),
    CONSTRAINT chk_feature_backfill_concurrency CHECK (max_concurrency > 0),
    CONSTRAINT chk_feature_backfill_times CHECK (jsonb_typeof(expanded_as_of_times) = 'array'),
    CONSTRAINT chk_feature_backfill_cutoff CHECK (jsonb_typeof(data_cutoff_policy) = 'object'),
    CONSTRAINT chk_feature_backfill_universe CHECK (jsonb_typeof(universe_request) = 'object'),
    CONSTRAINT chk_feature_backfill_status CHECK (
        status IN ('queued','running','succeeded','partially_succeeded','failed','cancelled')
    )
) TABLESPACE pg_default;

CREATE TABLE IF NOT EXISTS govern.feature_run (
    run_id                  UUID PRIMARY KEY,
    request_fingerprint     CHAR(64) NOT NULL,
    producer_service        VARCHAR(64) NOT NULL,
    producer_run_ref        VARCHAR(128) NOT NULL DEFAULT '',
    trigger_type            VARCHAR(32) NOT NULL,
    as_of_time              TIMESTAMPTZ NOT NULL,
    data_cutoff_time        TIMESTAMPTZ NOT NULL,
    source_profile          VARCHAR(64) NOT NULL DEFAULT 'default',
    market                  VARCHAR(32) NOT NULL DEFAULT '',
    universe_hash           CHAR(64) NOT NULL,
    request_payload         JSONB NOT NULL,
    code_revision           VARCHAR(128) NOT NULL,
    status                  VARCHAR(32) NOT NULL,
    retry_of_run_id         UUID REFERENCES govern.feature_run(run_id),
    worker_id               VARCHAR(128) NOT NULL DEFAULT '',
    heartbeat_at            TIMESTAMPTZ,
    backfill_id             UUID REFERENCES govern.feature_backfill_job(backfill_id),
    backfill_sequence       INTEGER,
    backfill_attempt        INTEGER,
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    error_code              VARCHAR(64) NOT NULL DEFAULT '',
    error_message           TEXT NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_feature_run_trigger
        CHECK (trigger_type IN ('manual','cron','api','backfill')),
    CONSTRAINT chk_feature_run_status CHECK (
        status IN ('queued','planning','running','validating','succeeded',
                   'partially_succeeded','failed','cancelled','aborted')
    ),
    CONSTRAINT chk_feature_run_time CHECK (data_cutoff_time <= as_of_time),
    CONSTRAINT chk_feature_run_payload CHECK (jsonb_typeof(request_payload) = 'object'),
    CONSTRAINT chk_feature_run_retry_not_self
        CHECK (retry_of_run_id IS NULL OR retry_of_run_id <> run_id),
    CONSTRAINT chk_feature_run_backfill_fields CHECK (
        (backfill_id IS NULL AND backfill_sequence IS NULL AND backfill_attempt IS NULL)
        OR
        (backfill_id IS NOT NULL AND backfill_sequence >= 0 AND backfill_attempt > 0)
    )
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_feature_run_lookup
    ON govern.feature_run (status, as_of_time DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feature_run_fingerprint
    ON govern.feature_run (request_fingerprint, status);

CREATE UNIQUE INDEX IF NOT EXISTS uk_feature_run_backfill_attempt
    ON govern.feature_run (backfill_id, as_of_time, backfill_attempt)
    WHERE backfill_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS govern.feature_run_item (
    run_id                  UUID NOT NULL REFERENCES govern.feature_run(run_id),
    feature_version_id      BIGINT NOT NULL REFERENCES govern.feature_version(id),
    status                  VARCHAR(32) NOT NULL,
    input_count             BIGINT NOT NULL DEFAULT 0,
    output_count            BIGINT NOT NULL DEFAULT 0,
    valid_count             BIGINT NOT NULL DEFAULT 0,
    missing_count           BIGINT NOT NULL DEFAULT 0,
    invalid_count           BIGINT NOT NULL DEFAULT 0,
    quality_summary         JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms             BIGINT NOT NULL DEFAULT 0,
    error_code              VARCHAR(64) NOT NULL DEFAULT '',
    error_message           TEXT NOT NULL DEFAULT '',
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    PRIMARY KEY (run_id, feature_version_id),
    CONSTRAINT chk_feature_run_item_status
        CHECK (status IN ('queued','running','validating','succeeded','failed','skipped')),
    CONSTRAINT chk_feature_run_item_counts CHECK (
        input_count >= 0 AND output_count >= 0 AND valid_count >= 0
        AND missing_count >= 0 AND invalid_count >= 0 AND duration_ms >= 0
    ),
    CONSTRAINT chk_feature_run_item_quality CHECK (jsonb_typeof(quality_summary) = 'object')
) TABLESPACE pg_default;

CREATE TABLE IF NOT EXISTS govern.feature_run_subject (
    run_id                  UUID NOT NULL REFERENCES govern.feature_run(run_id),
    security_id             BIGINT NOT NULL,
    symbol_snapshot         VARCHAR(32) NOT NULL DEFAULT '',
    exchange_snapshot       VARCHAR(16) NOT NULL DEFAULT '',
    asset_type_snapshot     VARCHAR(32) NOT NULL DEFAULT '',
    included_reason         VARCHAR(128) NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, security_id),
    CONSTRAINT chk_feature_run_subject_security CHECK (security_id > 0)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_feature_run_subject_security
    ON govern.feature_run_subject (security_id, run_id);

CREATE TABLE IF NOT EXISTS dwd.feature_value_numeric (
    run_id                      UUID NOT NULL,
    feature_version_id          BIGINT NOT NULL,
    security_id                 BIGINT NOT NULL,
    observed_at                 TIMESTAMPTZ NOT NULL,
    value                       DOUBLE PRECISION,
    value_status                VARCHAR(16) NOT NULL,
    quality_flags               JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_max_available_at     TIMESTAMPTZ,
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, feature_version_id, security_id, observed_at),
    CONSTRAINT chk_feature_numeric_status
        CHECK (value_status IN ('valid','missing','invalid')),
    CONSTRAINT chk_feature_numeric_value CHECK (
        (value_status = 'valid' AND value IS NOT NULL)
        OR (value_status IN ('missing','invalid') AND value IS NULL)
    ),
    CONSTRAINT chk_feature_numeric_finite CHECK (
        value IS NULL OR value NOT IN ('NaN'::float8, 'Infinity'::float8, '-Infinity'::float8)
    ),
    CONSTRAINT chk_feature_numeric_quality CHECK (jsonb_typeof(quality_flags) = 'object'),
    CONSTRAINT chk_feature_numeric_security CHECK (security_id > 0)
) TABLESPACE warm_storage;

SELECT create_hypertable(
    'dwd.feature_value_numeric',
    'observed_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_feature_numeric_series
    ON dwd.feature_value_numeric
       (feature_version_id, security_id, observed_at DESC, run_id);

CREATE INDEX IF NOT EXISTS idx_feature_numeric_cross_section
    ON dwd.feature_value_numeric
       (feature_version_id, observed_at DESC, run_id);

CREATE INDEX IF NOT EXISTS idx_feature_numeric_run
    ON dwd.feature_value_numeric (run_id, feature_version_id);

-- Stable definition identity: code and type semantics never mutate in place.
CREATE OR REPLACE FUNCTION govern.reject_feature_definition_identity_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (OLD.feature_code, OLD.kind, OLD.entity_type, OLD.value_type)
       IS DISTINCT FROM
       (NEW.feature_code, NEW.kind, NEW.entity_type, NEW.value_type) THEN
        RAISE EXCEPTION 'feature definition identity is immutable for %', OLD.feature_code;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_feature_definition_identity_immutable
    ON govern.feature_definition;
CREATE TRIGGER trg_feature_definition_identity_immutable
    BEFORE UPDATE ON govern.feature_definition
    FOR EACH ROW EXECUTE FUNCTION govern.reject_feature_definition_identity_change();

-- Published versions may only advance their lifecycle status/timestamps.
CREATE OR REPLACE FUNCTION govern.reject_published_feature_version_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'draft' AND (
        OLD.feature_id IS DISTINCT FROM NEW.feature_id
        OR OLD.version_number IS DISTINCT FROM NEW.version_number
        OR OLD.frequency IS DISTINCT FROM NEW.frequency
        OR OLD.as_of_semantics IS DISTINCT FROM NEW.as_of_semantics
        OR OLD.missing_policy IS DISTINCT FROM NEW.missing_policy
        OR OLD.manifest_checksum IS DISTINCT FROM NEW.manifest_checksum
        OR OLD.manifest_snapshot IS DISTINCT FROM NEW.manifest_snapshot
    ) THEN
        RAISE EXCEPTION 'published feature version % is immutable', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_feature_version_published_immutable
    ON govern.feature_version;
CREATE TRIGGER trg_feature_version_published_immutable
    BEFORE UPDATE ON govern.feature_version
    FOR EACH ROW EXECUTE FUNCTION govern.reject_published_feature_version_mutation();

CREATE OR REPLACE FUNCTION govern.reject_published_feature_child_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    version_id BIGINT;
    version_status VARCHAR(32);
BEGIN
    IF TG_OP = 'DELETE' THEN
        version_id := OLD.feature_version_id;
    ELSE
        version_id := NEW.feature_version_id;
    END IF;
    SELECT status INTO version_status
    FROM govern.feature_version WHERE id = version_id;
    IF version_status <> 'draft' THEN
        RAISE EXCEPTION 'children of published feature version % are immutable', version_id;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_feature_implementation_published_guard
    ON govern.feature_implementation;
CREATE TRIGGER trg_feature_implementation_published_guard
    BEFORE INSERT OR UPDATE OR DELETE ON govern.feature_implementation
    FOR EACH ROW EXECUTE FUNCTION govern.reject_published_feature_child_mutation();

DROP TRIGGER IF EXISTS trg_feature_dependency_published_guard
    ON govern.feature_dependency;
CREATE TRIGGER trg_feature_dependency_published_guard
    BEFORE INSERT OR UPDATE OR DELETE ON govern.feature_dependency
    FOR EACH ROW EXECUTE FUNCTION govern.reject_published_feature_child_mutation();

CREATE OR REPLACE FUNCTION dwd.enforce_feature_value_data_cutoff()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    run_cutoff TIMESTAMPTZ;
BEGIN
    SELECT data_cutoff_time INTO run_cutoff
    FROM govern.feature_run WHERE run_id = NEW.run_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'feature run % does not exist', NEW.run_id;
    END IF;
    IF NEW.source_max_available_at IS NOT NULL
       AND NEW.source_max_available_at > run_cutoff THEN
        RAISE EXCEPTION
            'source_max_available_at % exceeds data_cutoff_time % for run %',
            NEW.source_max_available_at, run_cutoff, NEW.run_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_feature_value_numeric_data_cutoff
    ON dwd.feature_value_numeric;
CREATE TRIGGER trg_feature_value_numeric_data_cutoff
    BEFORE INSERT ON dwd.feature_value_numeric
    FOR EACH ROW EXECUTE FUNCTION dwd.enforce_feature_value_data_cutoff();

CREATE OR REPLACE FUNCTION dwd.reject_feature_value_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'feature values are immutable; write a new run instead';
END;
$$;

DROP TRIGGER IF EXISTS trg_feature_value_numeric_immutable
    ON dwd.feature_value_numeric;
CREATE TRIGGER trg_feature_value_numeric_immutable
    BEFORE UPDATE OR DELETE ON dwd.feature_value_numeric
    FOR EACH ROW EXECUTE FUNCTION dwd.reject_feature_value_mutation();

COMMENT ON TABLE govern.feature_definition IS 'Feature Platform stable business identities.';
COMMENT ON TABLE govern.feature_version IS 'Immutable semantic versions; only lifecycle status may advance after publish.';
COMMENT ON TABLE govern.feature_dependency IS 'Exact FeatureVersion or governed DataField dependencies.';
COMMENT ON TABLE govern.feature_run IS 'Frozen Feature computation requests and reproducibility context.';
COMMENT ON TABLE govern.feature_backfill_job IS 'Persistent orchestration container for deterministic multi-date backfills.';
COMMENT ON TABLE dwd.feature_value_numeric IS 'Immutable numeric Feature values; visible by default only through succeeded runs.';
