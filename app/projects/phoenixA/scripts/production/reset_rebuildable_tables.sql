\set ON_ERROR_STOP on

-- DESTRUCTIVE: rebuild every PhoenixA-owned table except:
--   ods.security_registry
--   ods.research_report_download_record
--   ods._migrations
--
-- The caller must explicitly bind the target database name:
--   psql "$DATABASE_URL" -X \
--     -v confirm_reset=security_prod:RESET_NONCRITICAL \
--     -f scripts/production/reset_rebuildable_tables.sql

\if :{?confirm_reset}
\else
  \echo 'ERROR: pass -v confirm_reset=<database>:RESET_NONCRITICAL'
  \quit
\endif

SELECT :'confirm_reset' = current_database() || ':RESET_NONCRITICAL'
       AS reset_confirmed
\gset
\if :reset_confirmed
\else
  \echo 'ERROR: confirm_reset does not match current_database()'
  \quit
\endif

BEGIN;
SELECT pg_advisory_xact_lock(hashtext('phoenixA-production-rebaseline'));

DO $preflight$
DECLARE
    relation_record RECORD;
    relation_has_rows BOOLEAN;
BEGIN
    IF to_regclass('ods.security_registry') IS NULL
       OR to_regclass('ods.research_report_download_record') IS NULL
       OR to_regclass('ods._migrations') IS NULL THEN
        RAISE EXCEPTION
            'preserved tables are missing; aborting before destructive DDL';
    END IF;

    FOR relation_record IN
        SELECT n.nspname AS schema_name, c.relname AS relation_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('ods', 'dwd', 'govern', 'atlas_kg')
          AND c.relkind IN ('r', 'p')
          AND (n.nspname, c.relname) NOT IN (
              ('ods', 'security_registry'),
              ('ods', 'research_report_download_record'),
              ('ods', '_migrations'),
              ('govern', 'data_dataset_dictionary'),
              ('govern', 'data_field_dictionary'),
              ('govern', 'data_enum_dictionary')
          )
    LOOP
        EXECUTE format(
            'SELECT EXISTS (SELECT 1 FROM %I.%I LIMIT 1)',
            relation_record.schema_name,
            relation_record.relation_name
        ) INTO relation_has_rows;
        IF relation_has_rows THEN
            RAISE EXCEPTION
                'non-rebuildable data detected in %.%; review and back up before reset',
                relation_record.schema_name,
                relation_record.relation_name;
        END IF;
    END LOOP;
END
$preflight$;

CREATE TEMP TABLE phoenix_rebaseline_preserved_counts AS
SELECT
    (SELECT count(*) FROM ods.security_registry) AS security_registry_rows,
    (
        SELECT count(*)
        FROM ods.research_report_download_record
    ) AS research_report_rows;

DROP SCHEMA IF EXISTS dwd CASCADE;
DROP SCHEMA IF EXISTS govern CASCADE;
DROP SCHEMA IF EXISTS atlas_kg CASCADE;

DO $drop_ods$
DECLARE
    relation_record RECORD;
BEGIN
    FOR relation_record IN
        SELECT c.relkind, c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ods'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND c.relname NOT IN (
              'security_registry',
              'research_report_download_record',
              '_migrations'
          )
        ORDER BY
            CASE c.relkind WHEN 'v' THEN 1 WHEN 'm' THEN 2 ELSE 3 END,
            c.relname
    LOOP
        EXECUTE CASE relation_record.relkind
            WHEN 'v' THEN format(
                'DROP VIEW IF EXISTS ods.%I CASCADE',
                relation_record.relname
            )
            WHEN 'm' THEN format(
                'DROP MATERIALIZED VIEW IF EXISTS ods.%I CASCADE',
                relation_record.relname
            )
            WHEN 'f' THEN format(
                'DROP FOREIGN TABLE IF EXISTS ods.%I CASCADE',
                relation_record.relname
            )
            ELSE format(
                'DROP TABLE IF EXISTS ods.%I CASCADE',
                relation_record.relname
            )
        END;
    END LOOP;
END
$drop_ods$;

-- Rebuild the already-recorded 0001..0010 baseline from its clean definitions.
-- 0006 is intentionally idempotent against the preserved research-report table;
-- 0009 and 0010 are compatibility markers because their final shape is folded
-- into 0006.
\ir ../../migrations/postgresql/security/0001_ods.sql
\ir ../../migrations/postgresql/security/0002_dwd.sql
\ir ../../migrations/postgresql/security/0003_govern.sql
\ir ../../migrations/postgresql/security/0004_govern_seed.sql
\ir ../../migrations/postgresql/security/0005_govern_phoenixa_meta_enums.sql
\ir ../../migrations/postgresql/security/0006_research_report.sql
\ir ../../migrations/postgresql/security/0007_security_identity_stability.sql
\ir ../../migrations/postgresql/security/0008_feature_platform.sql
\ir ../../migrations/postgresql/security/0009_research_report_extra.sql
\ir ../../migrations/postgresql/security/0010_research_report_types.sql

DO $verify$
DECLARE
    expected_security_rows BIGINT;
    expected_report_rows BIGINT;
BEGIN
    SELECT security_registry_rows, research_report_rows
    INTO expected_security_rows, expected_report_rows
    FROM phoenix_rebaseline_preserved_counts;

    IF (SELECT count(*) FROM ods.security_registry) <> expected_security_rows THEN
        RAISE EXCEPTION 'security_registry row count changed during rebaseline';
    END IF;
    IF (
        SELECT count(*) FROM ods.research_report_download_record
    ) <> expected_report_rows THEN
        RAISE EXCEPTION
            'research_report_download_record row count changed during rebaseline';
    END IF;
END
$verify$;

COMMIT;

\echo 'Baseline 0001..0010 rebuilt. Start PhoenixA once to apply pending 0011+ migrations.'
