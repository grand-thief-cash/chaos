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
	Level      uint8     `gorm:"type:smallint;not null;default:0" json:"level"`
	IsLeaf     bool      `gorm:"type:boolean;not null;default:true" json:"is_leaf"`
	AttrsJSON  *string   `gorm:"column:attrs_json;type:jsonb" json:"attrs,omitempty"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (TaxonomyCategory) TableName() string { return "ods.taxonomy_category" }

// TaxonomySecurityMap maps a category to a security.
// Phase 2 surrogate-key refactor: pure (security_id, category_id) join table —
// the redundant source/taxonomy/category_code/symbol/asset_type/market columns
// were removed (refactor §2.3/§10.a). Provenance is recovered via category_id → taxonomy_category.
// Table: taxonomy_security_map
type TaxonomySecurityMap struct {
	SecurityID uint64    `gorm:"not null;primaryKey" json:"security_id"`
	CategoryID uint64    `gorm:"not null;primaryKey" json:"category_id"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at,omitempty"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at,omitempty"`
}

func (TaxonomySecurityMap) TableName() string { return "ods.taxonomy_security_map" }

// TaxonomyCategoryDerivedFlags stores PhoenixA-owned semantic derivations outside the ODS taxonomy table.
// Table: taxonomy_category_derived_flags
type TaxonomyCategoryDerivedFlags struct {
	ID           uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source       string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_tcdf_src_tax_mkt_code" json:"source"`
	Taxonomy     string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_tcdf_src_tax_mkt_code" json:"taxonomy"`
	Market       string    `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_tcdf_src_tax_mkt_code" json:"market"`
	Code         string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_tcdf_src_tax_mkt_code" json:"code"`
	DerivedFlags *string   `gorm:"column:derived_flags;type:jsonb" json:"derived_flags,omitempty"`
	CreatedAt    time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt    time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (TaxonomyCategoryDerivedFlags) TableName() string { return "dwd.taxonomy_category_derived_flags" }

// IndustryConstituent represents a constituent stock of an industry index.
// Phase 2 surrogate-key refactor: compressed to (category_id, security_id, in_date, out_date).
// IndexCode/ConCode/Symbol are input-only natural keys (gorm:"-"); phoenixA resolves them
// to CategoryID/SecurityID at upsert time via the in-memory resolve cache (refactor §2.3/§10.c).
// Table: industry_constituent
type IndustryConstituent struct {
	ID         uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	CategoryID uint64    `gorm:"not null;uniqueIndex:uk_cat_sec" json:"category_id"`
	SecurityID uint64    `gorm:"not null;uniqueIndex:uk_cat_sec" json:"security_id"`
	InDate     *string   `gorm:"type:varchar(10)" json:"in_date,omitempty"`
	OutDate    *string   `gorm:"type:varchar(10)" json:"out_date,omitempty"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	// Input-only natural keys (not persisted; resolved to CategoryID/SecurityID at upsert).
	IndexCode string `gorm:"-" json:"index_code,omitempty"`
	ConCode   string `gorm:"-" json:"con_code,omitempty"`
	Symbol    string `gorm:"-" json:"symbol,omitempty"`
}

func (IndustryConstituent) TableName() string { return "ods.industry_constituent" }

// IndustryWeight represents a daily weight of a constituent in an industry index.
// Phase 2 surrogate-key refactor: compressed to (category_id, security_id, trade_date, weight).
// Primary key is composite (category_id, security_id, trade_date) for TimescaleDB hypertable.
// IndexCode/ConCode/Symbol are input-only (gorm:"-").
// Table: industry_weight
type IndustryWeight struct {
	CategoryID uint64    `gorm:"not null;primaryKey" json:"category_id"`
	SecurityID uint64    `gorm:"not null;primaryKey" json:"security_id"`
	TradeDate  string    `gorm:"type:date;not null;primaryKey" json:"trade_date"`
	Weight     float64   `gorm:"type:decimal(10,6)" json:"weight"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	// Input-only natural keys (not persisted; resolved to CategoryID/SecurityID at upsert).
	IndexCode string `gorm:"-" json:"index_code,omitempty"`
	ConCode   string `gorm:"-" json:"con_code,omitempty"`
	Symbol    string `gorm:"-" json:"symbol,omitempty"`
}

func (IndustryWeight) TableName() string { return "ods.industry_weight" }

// IndustryDaily represents daily OHLCV + valuation data for an industry index.
// Phase 2 surrogate-key refactor: compressed to (category_id, trade_date, ...).
// Primary key is composite (category_id, trade_date) for TimescaleDB hypertable.
// Index-level data has no security_id. IndexCode is input-only (gorm:"-").
// Table: industry_daily
type IndustryDaily struct {
	CategoryID uint64    `gorm:"not null;primaryKey" json:"category_id"`
	TradeDate  string    `gorm:"type:date;not null;primaryKey" json:"trade_date"`
	Open       float64   `gorm:"type:decimal(20,4)" json:"open"`
	High       float64   `gorm:"type:decimal(20,4)" json:"high"`
	Close      float64   `gorm:"type:decimal(20,4)" json:"close"`
	Low        float64   `gorm:"type:decimal(20,4)" json:"low"`
	PreClose   float64   `gorm:"type:decimal(20,4)" json:"pre_close"`
	Amount     float64   `gorm:"type:decimal(20,4)" json:"amount"`
	Volume     float64   `gorm:"type:decimal(20,4)" json:"volume"`
	PB         float64   `gorm:"type:decimal(20,4)" json:"pb"`
	PE         float64   `gorm:"type:decimal(20,4)" json:"pe"`
	TotalCap   float64   `gorm:"type:decimal(20,4)" json:"total_cap"`
	AFloatCap  float64   `gorm:"type:decimal(20,4)" json:"a_float_cap"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	// Input-only natural key (not persisted; resolved to CategoryID at upsert).
	IndexCode string `gorm:"-" json:"index_code,omitempty"`
}

func (IndustryDaily) TableName() string { return "ods.industry_daily" }

// TaxonomyCategoryFilters for querying taxonomy categories.
type TaxonomyCategoryFilters struct {
	Source     string
	Taxonomy   string
	Market     string
	ParentCode *string
	Level      *uint8
	IsLeaf     *bool
	Name       string // LIKE match

	// ── JSONB filters (PostgreSQL-specific, leverages GIN index) ──
	// AttrsContains: JSONB @> containment, e.g. {"is_pub": 1} matches rows where attrs_json contains that key-value.
	AttrsContains map[string]interface{}
	// AttrsHasKey: JSONB ? operator, e.g. "change_reason" matches rows where attrs_json has that key.
	AttrsHasKey string
}

// TaxonomySecurityMapWithDetail is the response structure for GET /api/v2/taxonomy/by_security/{security_id}
// It includes fields from both taxonomy_security_map and taxonomy_category tables.
// Phase 2 surrogate-key refactor: keyed by security_id/category_id; the natural-key display
// fields (source/taxonomy/category_code/symbol/...) are populated by enriching the id-keyed
// mapping rows with taxonomy_category (looked up by category_id) + security_registry (resolved
// by security_id) at read time.
type TaxonomySecurityMapWithDetail struct {
	SecurityID   uint64 `json:"security_id"`
	CategoryID   uint64 `json:"category_id"`
	Source       string `json:"source"`
	Taxonomy     string `json:"taxonomy"`
	CategoryCode string `json:"category_code"`
	CategoryName string `json:"category_name"`
	Level        uint8  `json:"level"`
	ParentCode   string `json:"parent_code"`
	IndexCode    string `json:"index_code"`
	// Canonical fields provide a stable taxonomy-consumption view for downstream systems.
	CanonicalSource       string          `json:"canonical_source"`
	CanonicalTaxonomy     string          `json:"canonical_taxonomy"`
	CanonicalLevel        uint8           `json:"canonical_level"`
	CanonicalCategoryCode string          `json:"canonical_category_code"`
	CanonicalCategoryName string          `json:"canonical_category_name"`
	CanonicalParentCode   string          `json:"canonical_parent_code"`
	CanonicalIndexCode    string          `json:"canonical_index_code"`
	DerivedFlags          map[string]bool `json:"derived_flags"`
	Symbol                string          `json:"symbol"`
	AssetType             string          `json:"asset_type"`
	Market                string          `json:"market"`
	CreatedAt             time.Time       `json:"created_at,omitempty"`
	UpdatedAt             time.Time       `json:"updated_at,omitempty"`
}
