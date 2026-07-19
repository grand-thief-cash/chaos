package model

import (
	"encoding/json"
	"time"
)

// EquityStructure stores AmazingData get_equity_structure output.
// Table: equity_structure (migration 0014). Top-level columns hold the
// stable query dimensions (security_id, change_date, current_sign, is_valid);
// data_json holds the SDK detail fields governed by data_field_dictionary
// dataset=equity_structure.
// security_id is a logical FK to ods.security_registry.id (no real FK constraint, refactor §6 R9).
type EquityStructure struct {
	ID          uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID  uint64          `gorm:"column:security_id;not null;uniqueIndex:uk_equity_structure;index:idx_es_security_date" json:"security_id"`
	Source      string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_equity_structure" json:"source"`
	AnnDate     string          `gorm:"type:varchar(10);not null;default:'';uniqueIndex:uk_equity_structure" json:"ann_date"`
	ChangeDate  string          `gorm:"type:varchar(10);not null;uniqueIndex:uk_equity_structure;index:idx_es_security_date" json:"change_date"`
	CurrentSign int             `gorm:"type:smallint;not null;default:0" json:"current_sign"`
	IsValid     int             `gorm:"type:smallint;not null;default:1" json:"is_valid"`
	DataJSON    json.RawMessage `gorm:"column:data_json;type:jsonb;not null;default:'{}'" json:"data_json"`
	CreatedAt   time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (EquityStructure) TableName() string { return "ods.equity_structure" }

// EquityStructureFilters for querying equity_structure.
type EquityStructureFilters struct {
	SecurityID    uint64
	SecurityIDs   []uint64
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
