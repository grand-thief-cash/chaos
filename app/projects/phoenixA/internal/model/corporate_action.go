package model

import "time"

// CorporateAction stores corporate action data (dividend, right issue, etc.)
// using a JSON column for the variable data fields.
// Table: corporate_action
type CorporateAction struct {
	ID           uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source       string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_corp_action" json:"source"`
	Symbol       string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_corp_action;index:idx_symbol_action" json:"symbol"`
	Market       string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_corp_action" json:"market"`
	ActionType   string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_corp_action;index:idx_symbol_action" json:"action_type"` // dividend / right_issue
	ReportPeriod string    `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_corp_action;index:idx_report_period" json:"report_period"`
	AnnDate      string    `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_corp_action" json:"ann_date"`
	ProgressCode string    `gorm:"type:varchar(8);not null;default:''" json:"progress_code"`
	DataJSON     string    `gorm:"column:data_json;type:json;not null" json:"data_json"`
	CreatedAt    time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt    time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (CorporateAction) TableName() string { return "corporate_action" }

// CorporateActionFilters for querying corporate actions.
type CorporateActionFilters struct {
	Symbol       string
	Market       string
	ActionType   string
	ReportPeriod string
	PeriodStart  string
	PeriodEnd    string
	ProgressCode string
}
