package model

import (
	"encoding/json"
	"time"
)

// FinancialStatement stores financial statement data (balance sheet, income statement, cash flow)
// using a JSON column for the large number of numeric fields.
// Table: financial_statement
type FinancialStatement struct {
	ID              uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source          string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_fin_stmt" json:"source"`
	Symbol          string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_fin_stmt;index:idx_symbol_type" json:"symbol"`
	Market          string          `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_fin_stmt" json:"market"`
	StatementType   string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_fin_stmt;index:idx_symbol_type" json:"statement_type"` // balance_sheet / income / cashflow
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

func (FinancialStatement) TableName() string { return "financial_statement" }

// FinancialStatementFilters for querying financial statements.
type FinancialStatementFilters struct {
	Symbol           string
	Market           string
	StatementType    string
	ReportingPeriod  string   // exact match
	ReportingPeriods []string // batch: IN (...)
	PeriodStart      string   // range: >= this
	PeriodEnd        string   // range: <= this
	AnnDateBefore    string   // PIT filter: ann_date < this value (avoids look-ahead bias)
	ReportType       string
	CompTypeCode     *int
	// PostgreSQL JSONB filters
	DataContains map[string]interface{} // data_json @> '{"key": value}'  containment query
	DataHasKey   string                 // data_json ? 'key'  key existence check
}
