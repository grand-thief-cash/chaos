-- 0006_rename_timeframe_to_period.sql
-- Rename strategy_run_summary.timeframe → period
-- This is part of the unified field naming convention.

ALTER TABLE strategy_run_summary CHANGE COLUMN timeframe period VARCHAR(32) NOT NULL COMMENT 'K 线周期，如 daily (统一字段名)';

