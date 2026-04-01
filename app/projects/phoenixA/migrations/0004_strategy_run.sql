-- 0004_strategy_run.sql
-- Phase 1 historical backtest persistence tables for Artemis -> PhoenixA.

CREATE TABLE IF NOT EXISTS strategy_run_summary (
    run_id VARCHAR(128) NOT NULL,
    parent_run_id VARCHAR(128) NULL,
    task_code VARCHAR(64) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    strategy_code VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    timeframe VARCHAR(32) NOT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    start_cash DECIMAL(20,4) NULL,
    end_value DECIMAL(20,4) NULL,
    pnl DECIMAL(20,4) NULL,
    pnl_pct DECIMAL(20,6) NULL,
    max_drawdown DECIMAL(20,6) NULL,
    sharpe DECIMAL(20,6) NULL,
    trade_count INT NOT NULL DEFAULT 0,
    win_count INT NOT NULL DEFAULT 0,
    loss_count INT NOT NULL DEFAULT 0,
    win_rate DECIMAL(20,6) NULL,
    bars_processed INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    stop_reason VARCHAR(128) NULL,
    error_message TEXT NULL,
    duration_ms BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id),
    KEY idx_strategy_run_summary_parent_run_id (parent_run_id),
    KEY idx_strategy_run_summary_strategy_code (strategy_code),
    KEY idx_strategy_run_summary_symbol (symbol),
    KEY idx_strategy_run_summary_status (status),
    KEY idx_strategy_run_summary_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS strategy_run_artifact (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    run_id VARCHAR(128) NOT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    payload_json LONGTEXT NOT NULL,
    payload_version VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_strategy_run_artifact_run_type (run_id, artifact_type),
    KEY idx_strategy_run_artifact_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

