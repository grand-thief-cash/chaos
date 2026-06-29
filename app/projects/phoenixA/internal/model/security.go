package model

import "time"

// SecurityRegistry represents a tradable instrument in the unified security registry.
// Table: security_registry
type SecurityRegistry struct {
	Symbol     string    `gorm:"primaryKey;type:varchar(32);not null" json:"symbol"`
	AssetType  string    `gorm:"primaryKey;type:varchar(16);not null" json:"asset_type"`
	Market     string    `gorm:"primaryKey;type:varchar(16);not null" json:"market"`
	Exchange   string    `gorm:"type:varchar(8);not null" json:"exchange"`
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
	Symbol    string
	Symbols   []string
	AssetType string
	Market    string
	Exchange  string
	Exchanges []string
	Name      string
	Status    string
}
