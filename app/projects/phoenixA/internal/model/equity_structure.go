package model

import (
	"encoding/json"
	"time"
)

// EquityStructure stores AmazingData get_equity_structure output.
// Table: equity_structure (migration 0014). Top-level columns hold the
// stable query dimensions (symbol, change_date, current_sign, is_valid);
// data_json holds the SDK detail fields governed by data_field_dictionary
// dataset=equity_structure.
type EquityStructure struct {
	ID          uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source      string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_equity_structure" json:"source"`
	Symbol      string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_equity_structure;index:idx_es_symbol_date" json:"symbol"`
	Market      string          `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_equity_structure" json:"market"`
	AnnDate     string          `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_equity_structure" json:"ann_date"`
	ChangeDate  string          `gorm:"type:varchar(10);not null;uniqueIndex:uk_equity_structure;index:idx_es_symbol_date" json:"change_date"`
	CurrentSign int             `gorm:"type:smallint;not null;default:0" json:"current_sign"`
	IsValid     int             `gorm:"type:smallint;not null;default:1" json:"is_valid"`
	DataJSON    json.RawMessage `gorm:"column:data_json;type:jsonb;not null;default:'{}'" json:"data_json"`
	CreatedAt   time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (EquityStructure) TableName() string { return "equity_structure" }

// EquityStructureFilters for querying equity_structure.
type EquityStructureFilters struct {
	Symbol        string
	Symbols       []string
	Market        string
	ChangeDate    string   // exact match
	ChangeStart   string   // >=
	ChangeEnd     string   // <=
	AnnDateBefore string   // ann_date < this (PIT)
	CurrentOnly   bool     // current_sign = 1
	ValidOnly     bool     // is_valid = 1
	Fields        []string // requested field names (raw or canonical)
	DataContains  map[string]interface{}
	DataHasKey    string
}
