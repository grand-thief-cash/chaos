\set ON_ERROR_STOP on

-- Read-only inventory used before a PhoenixA production rebaseline.
-- Run with:
--   psql "$DATABASE_URL" -X -f scripts/production/audit_rebuild_scope.sql

\echo '== database and extensions =='
SELECT current_database() AS database_name,
       current_user AS database_user,
       current_setting('transaction_read_only') AS transaction_read_only,
       version() AS postgres_version;

SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('timescaledb', 'vector')
ORDER BY extname;

\echo '== exact rows by PhoenixA-owned relation =='
SELECT format(
           'SELECT %L AS relation, count(*) AS exact_rows FROM %I.%I;',
           n.nspname || '.' || c.relname,
           n.nspname,
           c.relname
       )
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('ods', 'dwd', 'govern', 'atlas_kg')
  AND c.relkind IN ('r', 'p')
ORDER BY n.nspname, c.relname
\gexec

\echo '== preserved table sizes =='
SELECT 'ods.security_registry' AS relation,
       count(*) AS exact_rows,
       pg_size_pretty(pg_total_relation_size('ods.security_registry')) AS total_size
FROM ods.security_registry
UNION ALL
SELECT 'ods.research_report_download_record',
       count(*),
       pg_size_pretty(
           pg_total_relation_size('ods.research_report_download_record')
       )
FROM ods.research_report_download_record;

\echo '== applied migrations =='
TABLE ods._migrations;

\echo '== invalid research-report security references =='
SELECT count(*) AS orphan_security_subjects
FROM ods.research_report_download_record r
LEFT JOIN ods.security_registry s ON s.id = r.subject_id
WHERE r.report_type IN ('stock', 'new_stock')
  AND r.subject_id IS NOT NULL
  AND s.id IS NULL;

\echo '== security_id columns without a registry foreign key =='
WITH security_columns AS (
    SELECT table_schema, table_name
    FROM information_schema.columns
    WHERE table_schema IN ('ods', 'dwd', 'govern', 'atlas_kg')
      AND column_name IN ('security_id', 'underlying_security_id')
),
registry_foreign_keys AS (
    SELECT ns.nspname AS table_schema, rel.relname AS table_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace ns ON ns.oid = rel.relnamespace
    WHERE con.contype = 'f'
      AND con.confrelid = 'ods.security_registry'::regclass
)
SELECT c.table_schema, c.table_name
FROM security_columns c
LEFT JOIN registry_foreign_keys f
  ON f.table_schema = c.table_schema
 AND f.table_name = c.table_name
WHERE f.table_name IS NULL
ORDER BY c.table_schema, c.table_name;
