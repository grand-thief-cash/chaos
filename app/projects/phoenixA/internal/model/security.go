package model

import "time"

// SecurityRegistry represents a tradable instrument in the unified security registry.
// Table: security_registry
//
// id is the surrogate primary key (BIGSERIAL), a proxy for the natural key
// (exchange, asset_type, symbol). Other tables reference it via security_id as
// a logical foreign key (no real FK constraint). id is stable only within the
// current rebuild cycle.
type SecurityRegistry struct {
	ID         uint64    `gorm:"primaryKey;autoIncrement" json:"security_id,omitempty"`
	Exchange   string    `gorm:"type:varchar(8);not null;uniqueIndex:uk_sr_exchange_asset_symbol" json:"exchange"`
	AssetType  string    `gorm:"type:varchar(16);not null;uniqueIndex:uk_sr_exchange_asset_symbol" json:"asset_type"`
	Symbol     string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_sr_exchange_asset_symbol" json:"symbol"`
	Market     string    `gorm:"type:varchar(16);not null;default:'zh_a'" json:"market"`
	Name       string    `gorm:"type:varchar(128);not null;default:''" json:"name"`
	FullName   *string   `gorm:"type:varchar(256)" json:"full_name,omitempty"`
	Status     string    `gorm:"type:varchar(16);not null;default:'active'" json:"status"`
	ListDate   *string   `gorm:"type:date" json:"list_date,omitempty"`
	DelistDate *string   `gorm:"type:date" json:"delist_date,omitempty"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (SecurityRegistry) TableName() string { return "ods.security_registry" }

// SecurityFilters for querying the security registry.
type SecurityFilters struct {
	SecurityID uint64
	Symbol     string
	Symbols    []string
	AssetType  string
	Market     string
	Exchange   string
	Exchanges  []string
	Name       string
	Status     string
	// Q is the unified free-text search term used by the general /securities
	// search endpoint and the autocomplete typeahead. Hit condition (any one
	// suffices, not both): symbol exact match (case-insensitive) OR name fuzzy
	// contains (case-sensitive). % and _ are treated as literals, not LIKE
	// wildcards. Distinct from the legacy exact `Symbol`/fuzzy `Name` params,
	// which stay for backward-compatible callers.
	Q string
}
