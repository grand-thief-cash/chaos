package model

import "time"

// StrategyRunSummary 存储单次策略回测的汇总结果，包括收益、风险指标和交易统计。
type StrategyRunSummary struct {
	RunID         string    `gorm:"primaryKey;column:run_id;type:varchar(128)" json:"run_id"`                    // 回测运行唯一标识，由 Artemis 生成
	ParentRunID   string    `gorm:"column:parent_run_id;type:varchar(128);index" json:"parent_run_id,omitempty"` // 父级 Campaign 运行 ID，单股票回测时为空
	TaskCode      string    `gorm:"column:task_code;type:varchar(64);not null" json:"task_code"`                 // 任务类型代码，如 BACKTRADER_RUN
	Mode          string    `gorm:"column:mode;type:varchar(32);not null" json:"mode"`                           // 回测模式，如 historical
	StrategyCode  string    `gorm:"column:strategy_code;type:varchar(64);not null;index" json:"strategy_code"`   // 策略代码，如 sma_cross
	Symbol        string    `gorm:"column:symbol;type:varchar(32);not null;index" json:"symbol"`                 // 股票代码，如 000001
	Timeframe     string    `gorm:"column:timeframe;type:varchar(32);not null" json:"timeframe"`                 // K 线周期，如 daily
	StartDate     string    `gorm:"column:start_date;type:date" json:"start_date,omitempty"`                     // 回测起始日期
	EndDate       string    `gorm:"column:end_date;type:date" json:"end_date,omitempty"`                         // 回测结束日期
	StartCash     float64   `gorm:"column:start_cash;type:decimal(20,4)" json:"start_cash"`                      // 初始资金
	EndValue      float64   `gorm:"column:end_value;type:decimal(20,4)" json:"end_value"`                        // 期末总资产
	Pnl           float64   `gorm:"column:pnl;type:decimal(20,4)" json:"pnl"`                                    // 盈亏金额 = EndValue - StartCash
	PnlPct        float64   `gorm:"column:pnl_pct;type:decimal(20,6)" json:"pnl_pct"`                            // 盈亏百分比 = Pnl / StartCash
	MaxDrawdown   float64   `gorm:"column:max_drawdown;type:decimal(20,6)" json:"max_drawdown"`                  // 最大回撤
	Sharpe        float64   `gorm:"column:sharpe;type:decimal(20,6)" json:"sharpe"`                              // 夏普比率
	TradeCount    int       `gorm:"column:trade_count" json:"trade_count"`                                       // 总交易次数
	WinCount      int       `gorm:"column:win_count" json:"win_count"`                                           // 盈利交易次数
	LossCount     int       `gorm:"column:loss_count" json:"loss_count"`                                         // 亏损交易次数
	WinRate       float64   `gorm:"column:win_rate;type:decimal(20,6)" json:"win_rate"`                          // 胜率 = WinCount / TradeCount
	BarsProcessed int       `gorm:"column:bars_processed" json:"bars_processed"`                                 // 处理的 K 线数量
	Status        string    `gorm:"column:status;type:varchar(32);not null;index" json:"status"`                 // 运行状态：SUCCESS / FAILED
	StopReason    string    `gorm:"column:stop_reason;type:varchar(128)" json:"stop_reason,omitempty"`           // 停止原因（如异常终止时的原因）
	ErrorMessage  string    `gorm:"column:error_message;type:text" json:"error_message,omitempty"`               // 错误信息
	DurationMs    int64     `gorm:"column:duration_ms" json:"duration_ms"`                                       // 执行耗时（毫秒）
	CreatedAt     time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`                          // 创建时间
	UpdatedAt     time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`                          // 更新时间
}

func (StrategyRunSummary) TableName() string { return "strategy_run_summary" }

// StrategyRunArtifact 存储回测产生的制品数据（分析结果、交易明细、权益曲线等）。
type StrategyRunArtifact struct {
	ID             uint64    `gorm:"primaryKey;autoIncrement;column:id" json:"id,omitempty"`                                                              // 自增主键
	RunID          string    `gorm:"column:run_id;type:varchar(128);not null;index:idx_strategy_run_artifact_run_type,unique" json:"run_id"`              // 关联的回测运行 ID
	ArtifactType   string    `gorm:"column:artifact_type;type:varchar(64);not null;index:idx_strategy_run_artifact_run_type,unique" json:"artifact_type"` // 制品类型：analyzers/trades/equity_curve/plot_manifest/plot_series 等
	PayloadJSON    string    `gorm:"column:payload_json;type:longtext;not null" json:"payload_json"`                                                      // 制品 JSON 数据
	PayloadVersion string    `gorm:"column:payload_version;type:varchar(32);not null" json:"payload_version"`                                             // 数据格式版本，如 v1
	CreatedAt      time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`                                                                  // 创建时间
	UpdatedAt      time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`                                                                  // 更新时间
}

func (StrategyRunArtifact) TableName() string { return "strategy_run_artifact" }

// StrategyRunSummaryFilters 用于查询回测汇总列表时的过滤条件。
type StrategyRunSummaryFilters struct {
	RunID        string // 按运行 ID 精确匹配
	ParentRunID  string // 按父级 Campaign 运行 ID 精确匹配
	StrategyCode string // 按策略代码过滤
	Symbol       string // 按股票代码过滤
	Status       string // 按运行状态过滤
}
