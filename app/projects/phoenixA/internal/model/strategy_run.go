package model

import "time"

type StrategyRunSummary struct {
	RunID         string    `gorm:"primaryKey;column:run_id;type:varchar(128)" json:"run_id"`
	ParentRunID   string    `gorm:"column:parent_run_id;type:varchar(128);index" json:"parent_run_id,omitempty"`
	TaskCode      string    `gorm:"column:task_code;type:varchar(64);not null" json:"task_code"`
	Mode          string    `gorm:"column:mode;type:varchar(32);not null" json:"mode"`
	StrategyCode  string    `gorm:"column:strategy_code;type:varchar(64);not null;index" json:"strategy_code"`
	Symbol        string    `gorm:"column:symbol;type:varchar(32);not null;index" json:"symbol"`
	Timeframe     string    `gorm:"column:timeframe;type:varchar(32);not null" json:"timeframe"`
	StartDate     string    `gorm:"column:start_date;type:date" json:"start_date,omitempty"`
	EndDate       string    `gorm:"column:end_date;type:date" json:"end_date,omitempty"`
	StartCash     float64   `gorm:"column:start_cash;type:decimal(20,4)" json:"start_cash"`
	EndValue      float64   `gorm:"column:end_value;type:decimal(20,4)" json:"end_value"`
	Pnl           float64   `gorm:"column:pnl;type:decimal(20,4)" json:"pnl"`
	PnlPct        float64   `gorm:"column:pnl_pct;type:decimal(20,6)" json:"pnl_pct"`
	MaxDrawdown   float64   `gorm:"column:max_drawdown;type:decimal(20,6)" json:"max_drawdown"`
	Sharpe        float64   `gorm:"column:sharpe;type:decimal(20,6)" json:"sharpe"`
	TradeCount    int       `gorm:"column:trade_count" json:"trade_count"`
	WinCount      int       `gorm:"column:win_count" json:"win_count"`
	LossCount     int       `gorm:"column:loss_count" json:"loss_count"`
	WinRate       float64   `gorm:"column:win_rate;type:decimal(20,6)" json:"win_rate"`
	BarsProcessed int       `gorm:"column:bars_processed" json:"bars_processed"`
	Status        string    `gorm:"column:status;type:varchar(32);not null;index" json:"status"`
	StopReason    string    `gorm:"column:stop_reason;type:varchar(128)" json:"stop_reason,omitempty"`
	ErrorMessage  string    `gorm:"column:error_message;type:text" json:"error_message,omitempty"`
	DurationMs    int64     `gorm:"column:duration_ms" json:"duration_ms"`
	CreatedAt     time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (StrategyRunSummary) TableName() string { return "strategy_run_summary" }

type StrategyRunArtifact struct {
	ID             uint64    `gorm:"primaryKey;autoIncrement;column:id" json:"id,omitempty"`
	RunID          string    `gorm:"column:run_id;type:varchar(128);not null;index:idx_strategy_run_artifact_run_type,unique" json:"run_id"`
	ArtifactType   string    `gorm:"column:artifact_type;type:varchar(64);not null;index:idx_strategy_run_artifact_run_type,unique" json:"artifact_type"`
	PayloadJSON    string    `gorm:"column:payload_json;type:longtext;not null" json:"payload_json"`
	PayloadVersion string    `gorm:"column:payload_version;type:varchar(32);not null" json:"payload_version"`
	CreatedAt      time.Time `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt      time.Time `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
}

func (StrategyRunArtifact) TableName() string { return "strategy_run_artifact" }

type StrategyRunSummaryFilters struct {
	RunID        string
	ParentRunID  string
	StrategyCode string
	Symbol       string
	Status       string
}
