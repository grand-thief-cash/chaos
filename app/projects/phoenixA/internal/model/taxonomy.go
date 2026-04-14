package model

import "time"

// TaxonomyCategory represents a unified classification node.
// Table: taxonomy_category
type TaxonomyCategory struct {
	ID         uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source     string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_source_code" json:"source"`
	Code       string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_source_code" json:"code"`
	Name       string    `gorm:"type:varchar(255);not null" json:"name"`
	ParentCode *string   `gorm:"type:varchar(64)" json:"parent_code,omitempty"`
	Level      uint8     `gorm:"type:tinyint unsigned;not null;default:0" json:"level"`
	IsLeaf     bool      `gorm:"type:tinyint(1);not null;default:1" json:"is_leaf"`
	AttrsJSON  *string   `gorm:"column:attrs_json;type:json" json:"attrs,omitempty"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (TaxonomyCategory) TableName() string { return "taxonomy_category" }

// TaxonomySecurityMap maps a category to a security.
// Table: taxonomy_security_map
type TaxonomySecurityMap struct {
	Source       string `gorm:"type:varchar(32);not null;uniqueIndex:uk_source_cat_sec" json:"source"`
	CategoryCode string `gorm:"type:varchar(64);not null;uniqueIndex:uk_source_cat_sec" json:"category_code"`
	Symbol       string `gorm:"type:varchar(32);not null;uniqueIndex:uk_source_cat_sec" json:"symbol"`
	AssetType    string `gorm:"type:varchar(16);not null;default:'stock';uniqueIndex:uk_source_cat_sec" json:"asset_type"`
	Market       string `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_source_cat_sec" json:"market"`
}

func (TaxonomySecurityMap) TableName() string { return "taxonomy_security_map" }

// TaxonomyCategoryFilters for querying taxonomy categories.
type TaxonomyCategoryFilters struct {
	Source     string
	ParentCode *string
	Level      *uint8
	IsLeaf     *bool
	Name       string // LIKE match
}
