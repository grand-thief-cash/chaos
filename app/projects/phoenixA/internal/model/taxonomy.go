package model

import "time"

// TaxonomyCategory represents a unified classification node.
// Table: taxonomy_category
type TaxonomyCategory struct {
	ID         uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source     string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_mkt_code" json:"source"`
	Taxonomy   string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_mkt_code" json:"taxonomy"`
	Market     string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_src_tax_mkt_code" json:"market"`
	Code       string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_src_tax_mkt_code" json:"code"`
	Name       string    `gorm:"type:varchar(255);not null" json:"name"`
	ParentCode *string   `gorm:"type:varchar(64)" json:"parent_code,omitempty"`
	IndexCode  *string   `gorm:"type:varchar(64)" json:"index_code,omitempty"`
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
	Source       string `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_cat_sec" json:"source"`
	Taxonomy     string `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_cat_sec" json:"taxonomy"`
	CategoryCode string `gorm:"type:varchar(64);not null;uniqueIndex:uk_src_tax_cat_sec" json:"category_code"`
	Symbol       string `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_cat_sec" json:"symbol"`
	AssetType    string `gorm:"type:varchar(16);not null;default:'stock';uniqueIndex:uk_src_tax_cat_sec" json:"asset_type"`
	Market       string `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_src_tax_cat_sec" json:"market"`
}

func (TaxonomySecurityMap) TableName() string { return "taxonomy_security_map" }

// IndustryConstituent represents a constituent stock of an industry index.
// Table: industry_constituent
type IndustryConstituent struct {
	ID        uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source    string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym" json:"source"`
	Taxonomy  string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym" json:"taxonomy"`
	Market    string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_src_tax_idx_sym" json:"market"`
	IndexCode string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_src_tax_idx_sym" json:"index_code"`
	ConCode   string    `gorm:"type:varchar(64);not null;default:''" json:"con_code"`
	Symbol    string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym" json:"symbol"`
	IndexName string    `gorm:"type:varchar(255);not null;default:''" json:"index_name"`
	InDate    *string   `gorm:"type:varchar(10)" json:"in_date,omitempty"`
	OutDate   *string   `gorm:"type:varchar(10)" json:"out_date,omitempty"`
	CreatedAt time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (IndustryConstituent) TableName() string { return "industry_constituent" }

// IndustryWeight represents a daily weight of a constituent in an industry index.
// Table: industry_weight
type IndustryWeight struct {
	ID        uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source    string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym_dt" json:"source"`
	Taxonomy  string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym_dt" json:"taxonomy"`
	Market    string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_src_tax_idx_sym_dt" json:"market"`
	IndexCode string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_src_tax_idx_sym_dt" json:"index_code"`
	ConCode   string    `gorm:"type:varchar(64);not null;default:''" json:"con_code"`
	Symbol    string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_sym_dt" json:"symbol"`
	TradeDate string    `gorm:"type:varchar(10);not null;uniqueIndex:uk_src_tax_idx_sym_dt" json:"trade_date"`
	Weight    float64   `gorm:"type:decimal(10,6)" json:"weight"`
	CreatedAt time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (IndustryWeight) TableName() string { return "industry_weight" }

// IndustryDaily represents daily OHLCV + valuation data for an industry index.
// Table: industry_daily
type IndustryDaily struct {
	ID        uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source    string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_mkt_dt" json:"source"`
	Taxonomy  string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_src_tax_idx_mkt_dt" json:"taxonomy"`
	Market    string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_src_tax_idx_mkt_dt" json:"market"`
	IndexCode string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_src_tax_idx_mkt_dt" json:"index_code"`
	TradeDate string    `gorm:"type:varchar(10);not null;uniqueIndex:uk_src_tax_idx_mkt_dt" json:"trade_date"`
	Open      float64   `gorm:"type:decimal(20,4)" json:"open"`
	High      float64   `gorm:"type:decimal(20,4)" json:"high"`
	Close     float64   `gorm:"type:decimal(20,4)" json:"close"`
	Low       float64   `gorm:"type:decimal(20,4)" json:"low"`
	PreClose  float64   `gorm:"type:decimal(20,4)" json:"pre_close"`
	Amount    float64   `gorm:"type:decimal(20,4)" json:"amount"`
	Volume    float64   `gorm:"type:decimal(20,4)" json:"volume"`
	PB        float64   `gorm:"type:decimal(20,4)" json:"pb"`
	PE        float64   `gorm:"type:decimal(20,4)" json:"pe"`
	TotalCap  float64   `gorm:"type:decimal(20,4)" json:"total_cap"`
	AFloatCap float64   `gorm:"type:decimal(20,4)" json:"a_float_cap"`
	CreatedAt time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (IndustryDaily) TableName() string { return "industry_daily" }

// TaxonomyCategoryFilters for querying taxonomy categories.
type TaxonomyCategoryFilters struct {
	Source     string
	Taxonomy   string
	Market     string
	ParentCode *string
	Level      *uint8
	IsLeaf     *bool
	Name       string // LIKE match
}
