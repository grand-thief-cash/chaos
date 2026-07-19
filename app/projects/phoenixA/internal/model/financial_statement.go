package model

import (
	"encoding/json"
	"time"
)

// FinancialStatement stores financial statement data (balance sheet, income statement, cash flow)
// using a JSON column for the large number of numeric fields.
// Table: financial_statement
// security_id is a logical FK to ods.security_registry.id (no real FK constraint, refactor §6 R9).
type FinancialStatement struct {
	ID              uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID      uint64          `gorm:"column:security_id;not null;uniqueIndex:uk_fin_stmt;index:idx_security_type" json:"security_id"`
	Source          string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_fin_stmt" json:"source"`
	StatementType   string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_fin_stmt;index:idx_security_type" json:"statement_type"` // balance_sheet / income / cashflow
	ReportingPeriod string          `gorm:"type:varchar(10);not null;uniqueIndex:uk_fin_stmt;index:idx_report_period" json:"reporting_period"`
	ReportType      string          `gorm:"type:varchar(32);not null;default:'';uniqueIndex:uk_fin_stmt" json:"report_type"`    // 报告期名称
	StatementCode   string          `gorm:"type:varchar(32);not null;default:'';uniqueIndex:uk_fin_stmt" json:"statement_code"` // 报表类型代码
	SecurityName    string          `gorm:"type:varchar(128);not null;default:''" json:"security_name"`
	AnnDate         string          `gorm:"type:varchar(10);not null;default:''" json:"ann_date"`
	ActualAnnDate   string          `gorm:"type:varchar(10);not null;default:''" json:"actual_ann_date"`
	CompTypeCode    int             `gorm:"type:smallint;not null;default:0" json:"comp_type_code"` // 1:非金融 2:银行 3:保险 4:证券
	DataJSON        json.RawMessage `gorm:"column:data_json;type:jsonb;not null;default:'{}'" json:"data_json"`
	CreatedAt       time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (FinancialStatement) TableName() string { return "ods.financial_statement" }

// FinancialStatementFilters for querying financial statements.
type FinancialStatementFilters struct {
	SecurityID       uint64
	SecurityIDs      []uint64 // batch query for multiple securities
	StatementType    string
	StatementCode    string   // report type code (e.g., "合并报表", "母公司报表")
	ReportingPeriod  string   // exact match
	ReportingPeriods []string // batch: IN (...)
	PeriodStart      string   // range: >= this
	PeriodEnd        string   // range: <= this
	AnnDateBefore    string   // PIT filter: ann_date < this value (avoids look-ahead bias)
	ReportType       string
	CompTypeCode     *int
	Fields           []string // fields to return (e.g., ["security_id", "data_json->TOTAL_ASSETS"])
	// PostgreSQL JSONB filters
	DataContains map[string]interface{} // data_json @> '{"key": value}'  containment query
	DataHasKey   string                 // data_json ? 'key'  key existence check
}
