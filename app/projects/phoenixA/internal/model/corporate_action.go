package model

import (
	"encoding/json"
	"time"
)

// CorporateAction stores corporate action data (dividend, right issue, etc.)
// using a JSON column for the variable data fields.
// Table: corporate_action
// security_id is a logical FK to ods.security_registry.id (no real FK constraint, refactor §6 R9).
type CorporateAction struct {
	ID           uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID   uint64          `gorm:"column:security_id;not null;uniqueIndex:uk_corp_action;index:idx_security_action" json:"security_id"`
	Source       string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_corp_action" json:"source"`
	ActionType   string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_corp_action;index:idx_security_action" json:"action_type"` // dividend / right_issue
	ReportPeriod string          `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_corp_action;index:idx_report_period" json:"report_period"`
	AnnDate      string          `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_corp_action" json:"ann_date"`
	ProgressCode string          `gorm:"type:varchar(8);not null;default:''" json:"progress_code"`
	DataJSON     json.RawMessage `gorm:"column:data_json;type:jsonb;not null;default:'{}'" json:"data_json"`
	CreatedAt    time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt    time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (CorporateAction) TableName() string { return "ods.corporate_action" }

// CorporateActionFilters for querying corporate actions.
type CorporateActionFilters struct {
	SecurityID    uint64
	SecurityIDs   []uint64 // batch query for multiple securities
	ActionType    string
	ReportPeriod  string
	PeriodStart   string
	PeriodEnd     string
	AnnDateBefore string
	ProgressCode  string
	Fields        []string // fields to return (e.g., ["security_id", "data_json->DVD_PER_SHARE_PRE_TAX_CASH"])
	// PostgreSQL JSONB filters
	DataContains map[string]interface{} // data_json @> '{"key": value}'  containment query
	DataHasKey   string                 // data_json ? 'key'  key existence check
}
