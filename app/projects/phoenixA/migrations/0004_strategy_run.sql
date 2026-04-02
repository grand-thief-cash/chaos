-- 0004_strategy_run.sql
-- Phase 1 historical backtest persistence tables for Artemis -> PhoenixA.

CREATE TABLE IF NOT EXISTS strategy_run_summary (
    run_id VARCHAR(128) NOT NULL COMMENT '回测运行唯一标识，由 Artemis 生成',
    parent_run_id VARCHAR(128) NULL COMMENT '父级 Campaign 运行 ID，单股票回测时为空',
    task_code VARCHAR(64) NOT NULL COMMENT '任务类型代码，如 BACKTRADER_RUN',
    mode VARCHAR(32) NOT NULL COMMENT '回测模式，如 historical',
    strategy_code VARCHAR(64) NOT NULL COMMENT '策略代码，如 sma_cross',
    symbol VARCHAR(32) NOT NULL COMMENT '股票代码，如 000001',
    timeframe VARCHAR(32) NOT NULL COMMENT 'K 线周期，如 daily',
    start_date DATE NULL COMMENT '回测起始日期',
    end_date DATE NULL COMMENT '回测结束日期',
    start_cash DECIMAL(20,4) NULL COMMENT '初始资金',
    end_value DECIMAL(20,4) NULL COMMENT '期末总资产',
    pnl DECIMAL(20,4) NULL COMMENT '盈亏金额 = end_value - start_cash',
    pnl_pct DECIMAL(20,6) NULL COMMENT '盈亏百分比 = pnl / start_cash',
    max_drawdown DECIMAL(20,6) NULL COMMENT '最大回撤',
    sharpe DECIMAL(20,6) NULL COMMENT '夏普比率',
    trade_count INT NOT NULL DEFAULT 0 COMMENT '总交易次数',
    win_count INT NOT NULL DEFAULT 0 COMMENT '盈利交易次数',
    loss_count INT NOT NULL DEFAULT 0 COMMENT '亏损交易次数',
    win_rate DECIMAL(20,6) NULL COMMENT '胜率 = win_count / trade_count',
    bars_processed INT NOT NULL DEFAULT 0 COMMENT '处理的 K 线数量',
    status VARCHAR(32) NOT NULL COMMENT '运行状态：SUCCESS / FAILED',
    stop_reason VARCHAR(128) NULL COMMENT '停止原因',
    error_message TEXT NULL COMMENT '错误信息',
    duration_ms BIGINT NOT NULL DEFAULT 0 COMMENT '执行耗时（毫秒）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (run_id),
    KEY idx_strategy_run_summary_parent_run_id (parent_run_id),
    KEY idx_strategy_run_summary_strategy_code (strategy_code),
    KEY idx_strategy_run_summary_symbol (symbol),
    KEY idx_strategy_run_summary_status (status),
    KEY idx_strategy_run_summary_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略回测汇总结果表';

CREATE TABLE IF NOT EXISTS strategy_run_artifact (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    run_id VARCHAR(128) NOT NULL COMMENT '关联的回测运行 ID',
    artifact_type VARCHAR(64) NOT NULL COMMENT '制品类型：analyzers/trades/equity_curve/plot_manifest/plot_series 等',
    payload_json LONGTEXT NOT NULL COMMENT '制品 JSON 数据',
    payload_version VARCHAR(32) NOT NULL COMMENT '数据格式版本，如 v1',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_strategy_run_artifact_run_type (run_id, artifact_type),
    KEY idx_strategy_run_artifact_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略回测制品数据表';

