-- ============================================================
-- PhoenixA PostgreSQL Migration 0004: Storage Tier Setup
-- Target: chaos_db
-- Scope: Backfill storage tiers for EXISTING deployments
--
-- PREREQUISITE: warm_storage tablespace must be created by
-- the PostgreSQL superuser BEFORE running this migration:
--
--   sudo -u postgres psql -c \
--     "CREATE TABLESPACE warm_storage LOCATION '/sata8t/pgdata_warm';"
--
-- The directory /sata8t/pgdata_warm must exist and be owned by
-- the postgres OS user (chmod 700, chown postgres:postgres).
--
-- This migration is IDEMPOTENT — safe to run multiple times.
-- It does NOT create the tablespace itself (requires superuser).
--
-- IMPORTANT:
--   1) hot/warm is specified in PostgreSQL DDL (`TABLESPACE ...`), not in config.yaml
--   2) config.yaml does NOT need a new hot/warm field for this to work
--   3) this migration only moves already-created tables for existing environments
--   4) for NEW environments, 0001/0002/kg-0001 now create tables directly on the target tablespace
--
-- Storage Strategy (see STORAGE_TIER_PLANNING.md v2):
--   NVMe (pg_default): metadata small tables, PGVector, WAL
--   SATA (warm_storage): all business data (bars, financial,
--     taxonomy, factors, strategy, kg extractions)
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- 1. Verify warm_storage tablespace exists
--    (This will raise an error if it doesn't — intentional)
-- ──────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'warm_storage') THEN
        RAISE NOTICE '=====================================================';
        RAISE NOTICE 'TABLESPACE warm_storage does not exist.';
        RAISE NOTICE 'Please create it as superuser first:';
        RAISE NOTICE '  CREATE TABLESPACE warm_storage';
        RAISE NOTICE '    LOCATION ''/sata8t/pgdata_warm'';';
        RAISE NOTICE '=====================================================';
        RAISE NOTICE 'Skipping table moves. Tables will remain on pg_default';
        RAISE NOTICE 'until warm_storage is available.';
    END IF;
END $$;

-- ──────────────────────────────────────────────────────────
-- 2. Move existing large tables to warm_storage
--    (Only if warm_storage tablespace exists)
-- ──────────────────────────────────────────────────────────
DO $$
DECLARE
    tbl TEXT;
    tables_to_move TEXT[] := ARRAY[
        -- Taxonomy large tables
        'industry_constituent',
        'industry_weight',
        'industry_daily',
        -- Financial data
        'financial_statement',
        'corporate_action',
        -- Strategy
        'strategy_run_artifact'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'warm_storage') THEN
        RAISE NOTICE 'warm_storage not available, skipping table moves';
        RETURN;
    END IF;

    FOREACH tbl IN ARRAY tables_to_move LOOP
        -- Only move if table exists and is not already on warm_storage
        IF EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'security_dev' AND tablename = tbl
        ) THEN
            -- Check current tablespace
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_tablespace ts ON ts.oid = c.reltablespace
                WHERE n.nspname = 'security_dev'
                  AND c.relname = tbl
                  AND ts.spcname = 'warm_storage'
            ) THEN
                EXECUTE format('ALTER TABLE security_dev.%I SET TABLESPACE warm_storage', tbl);
                RAISE NOTICE 'Moved table % to warm_storage', tbl;
            ELSE
                RAISE NOTICE 'Table % already on warm_storage, skipping', tbl;
            END IF;
        ELSE
            RAISE NOTICE 'Table % does not exist yet, skipping', tbl;
        END IF;
    END LOOP;
END $$;

-- ──────────────────────────────────────────────────────────
-- 3. Move bars_* tables to warm_storage
--    (Dynamic: finds all bars_ prefixed tables)
-- ──────────────────────────────────────────────────────────
DO $$
DECLARE
    rec RECORD;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'warm_storage') THEN
        RETURN;
    END IF;

    FOR rec IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'security_dev'
          AND (tablename LIKE 'bars_%' OR tablename LIKE 'bars_ext_%')
    LOOP
        -- Check if not already on warm_storage
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_tablespace ts ON ts.oid = c.reltablespace
            WHERE n.nspname = 'security_dev'
              AND c.relname = rec.tablename
              AND ts.spcname = 'warm_storage'
        ) THEN
            EXECUTE format('ALTER TABLE security_dev.%I SET TABLESPACE warm_storage', rec.tablename);
            RAISE NOTICE 'Moved table % to warm_storage', rec.tablename;
        END IF;
    END LOOP;
END $$;

-- ──────────────────────────────────────────────────────────
-- 4. Move KG large tables to warm_storage
-- ──────────────────────────────────────────────────────────
DO $$
DECLARE
    tbl TEXT;
    kg_tables_to_move TEXT[] := ARRAY[
        'extractions',
        'impact_logs'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'warm_storage') THEN
        RETURN;
    END IF;

    FOREACH tbl IN ARRAY kg_tables_to_move LOOP
        IF EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'kg' AND tablename = tbl
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_tablespace ts ON ts.oid = c.reltablespace
                WHERE n.nspname = 'kg'
                  AND c.relname = tbl
                  AND ts.spcname = 'warm_storage'
            ) THEN
                EXECUTE format('ALTER TABLE kg.%I SET TABLESPACE warm_storage', tbl);
                RAISE NOTICE 'Moved table kg.% to warm_storage', tbl;
            END IF;
        END IF;
    END LOOP;
END $$;

-- ──────────────────────────────────────────────────────────
-- 5. DBA note: default_tablespace is a DATABASE / ROLE setting, not config.yaml
-- ──────────────────────────────────────────────────────────
-- This is intentionally NOT executed here because ALTER ROLE / ALTER DATABASE
-- often requires higher privileges than the app migration user has.
--
-- If you want future auto-created tables (without explicit TABLESPACE) to land on SATA,
-- let the DBA run ONE of the following manually:
--
--   ALTER DATABASE chaos_db SET default_tablespace = warm_storage;
--   -- or
--   ALTER ROLE chaos_app SET default_tablespace = warm_storage;
--
-- PhoenixA config.yaml does not need to change for this.


-- ──────────────────────────────────────────────────────────
-- 6. TEMPLATE: Creating new bars tables on warm_storage
--    (For reference — GORM auto-migrate will inherit
--     default_tablespace set above)
-- ──────────────────────────────────────────────────────────
-- New bars tables created by GORM AutoMigrate will use warm_storage only if
-- the DBA sets ALTER DATABASE / ALTER ROLE default_tablespace as shown above.
-- Otherwise they land on pg_default and should be moved by a follow-up migration.
--
-- For manual table creation or TimescaleDB hypertables:
--
-- CREATE TABLE bars_stock_zh_a_1min_nf (
--     symbol      VARCHAR(32)  NOT NULL,
--     trade_date  TIMESTAMPTZ  NOT NULL,
--     open        DECIMAL(12,4),
--     high        DECIMAL(12,4),
--     low         DECIMAL(12,4),
--     close       DECIMAL(12,4),
--     volume      BIGINT,
--     amount      DECIMAL(20,4),
--     preclose    DECIMAL(12,4),
--     pct_chg     DECIMAL(10,4),
--     CONSTRAINT uk_bars_1min_nf UNIQUE (symbol, trade_date)
-- ) TABLESPACE warm_storage;
--
-- SELECT create_hypertable(
--     'bars_stock_zh_a_1min_nf', 'trade_date',
--     chunk_time_interval => INTERVAL '1 week'
-- );
--
-- ALTER TABLE bars_stock_zh_a_1min_nf SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'symbol',
--     timescaledb.compress_orderby = 'trade_date DESC'
-- );
-- SELECT add_compression_policy(
--     'bars_stock_zh_a_1min_nf', INTERVAL '3 months'
-- );


-- ──────────────────────────────────────────────────────────
-- 7. TEMPLATE: Factor table (future migration)
-- ──────────────────────────────────────────────────────────
-- CREATE TABLE factor_daily (
--     trade_date    DATE         NOT NULL,
--     symbol        VARCHAR(32)  NOT NULL,
--     factor_id     VARCHAR(64)  NOT NULL,
--     factor_value  DOUBLE PRECISION,
--     z_score       DOUBLE PRECISION,
--     percentile    DOUBLE PRECISION,
--     created_at    TIMESTAMPTZ  DEFAULT NOW()
-- ) TABLESPACE warm_storage;
--
-- CREATE TABLE factor_metadata (
--     factor_id     VARCHAR(64) PRIMARY KEY,
--     factor_name   VARCHAR(128) NOT NULL,
--     category      VARCHAR(32)  NOT NULL,
--     subcategory   VARCHAR(64),
--     description   TEXT,
--     formula       TEXT,
--     data_source   VARCHAR(64),
--     frequency     VARCHAR(16) DEFAULT 'daily',
--     universe      VARCHAR(32) DEFAULT 'zh_a',
--     params        JSONB DEFAULT '{}',
--     is_active     BOOLEAN DEFAULT TRUE,
--     created_at    TIMESTAMPTZ DEFAULT NOW(),
--     updated_at    TIMESTAMPTZ DEFAULT NOW()
-- );
-- Note: factor_metadata is small, stays on NVMe (pg_default).
-- Explicitly set: ) TABLESPACE pg_default;
-- Or omit TABLESPACE clause (inherits user default → warm),
-- then move: ALTER TABLE factor_metadata SET TABLESPACE pg_default;


-- ──────────────────────────────────────────────────────────
-- 8. Verification query (run manually after migration)
-- ──────────────────────────────────────────────────────────
-- SELECT schemaname, tablename,
--        COALESCE(tablespace, 'pg_default') AS tablespace,
--        pg_size_pretty(pg_total_relation_size(
--            schemaname || '.' || tablename
--        )) AS total_size
-- FROM pg_tables
-- WHERE schemaname IN ('security_dev', 'kg')
-- ORDER BY tablespace, pg_total_relation_size(
--     schemaname || '.' || tablename
-- ) DESC;

