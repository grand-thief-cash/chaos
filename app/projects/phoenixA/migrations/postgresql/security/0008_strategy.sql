-- ============================================================
-- PhoenixA PostgreSQL Migration 0008: Strategy Backtest Tables
-- Target: chaos_db, schema: security_dev
-- Scope: strategy_run_summary, strategy_run_artifact
--
-- Strategy backtesting results written by Athena (strategy engine)
-- via PhoenixA REST API.
--
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - strategy_run_summary   -> pg_default (NVMe, ~0.5 GB, list queries)
--   - strategy_run_artifact  -> warm_storage (SATA, ~50-500 GB, large JSON)
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- 1. strategy_run_summary
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_run_summary (
    run_id         VARCHAR(128)   PRIMARY KEY,
    parent_run_id  VARCHAR(128),
    task_code      VARCHAR(64)    NOT NULL,
    mode           VARCHAR(32)    NOT NULL,
    strategy_code  VARCHAR(64)    NOT NULL,
    symbol         VARCHAR(32)    NOT NULL,
    period         VARCHAR(32)    NOT NULL,
    start_date     DATE,
    end_date       DATE,
    start_cash     DECIMAL(20,4),
    end_value      DECIMAL(20,4),
    pnl            DECIMAL(20,4),
    pnl_pct        DECIMAL(20,6),
    max_drawdown   DECIMAL(20,6),
    sharpe         DECIMAL(20,6),
    trade_count    INT            NOT NULL DEFAULT 0,
    win_count      INT            NOT NULL DEFAULT 0,
    loss_count     INT            NOT NULL DEFAULT 0,
    win_rate       DECIMAL(20,6),
    bars_processed INT            NOT NULL DEFAULT 0,
    status         VARCHAR(32)    NOT NULL,
    stop_reason    VARCHAR(128),
    error_message  TEXT,
    duration_ms    BIGINT         NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW()
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_srs_parent_run_id
    ON strategy_run_summary (parent_run_id)
    WHERE parent_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_srs_strategy_code
    ON strategy_run_summary (strategy_code);
CREATE INDEX IF NOT EXISTS idx_srs_symbol
    ON strategy_run_summary (symbol);
CREATE INDEX IF NOT EXISTS idx_srs_status
    ON strategy_run_summary (status);
CREATE INDEX IF NOT EXISTS idx_srs_created_at
    ON strategy_run_summary (created_at);

-- ──────────────────────────────────────────────────────────
-- 2. strategy_run_artifact
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_run_artifact (
    id              BIGSERIAL      PRIMARY KEY,
    run_id          VARCHAR(128)   NOT NULL,
    artifact_type   VARCHAR(64)    NOT NULL,
    payload_json    JSONB          NOT NULL DEFAULT '{}',
    payload_version VARCHAR(32)    NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_sra_run_type UNIQUE (run_id, artifact_type)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_sra_run_id
    ON strategy_run_artifact (run_id) TABLESPACE warm_storage;

-- GIN index on JSONB payload for ad-hoc queries
CREATE INDEX IF NOT EXISTS idx_sra_payload_gin
    ON strategy_run_artifact USING GIN (payload_json jsonb_path_ops) TABLESPACE warm_storage;
