package model

import (
	"encoding/json"
	"time"
)

// ─── Field Dictionary Models ───
//
// Mirrors the dictionary tables created by migration 0012_field_dictionary.sql
// and seeded by 0013_seed_amazing_data_field_dictionary.sql. These are the
// authoritative machine-readable field contracts exposed via the
// /api/v2/catalog/datasets, /datasets/{dataset}/fields and /enums/{enum_name}
// discovery APIs (Phase 2 of the AmazingData field discovery design).

// DatasetDictionaryEntry mirrors a row in data_dataset_dictionary.
type DatasetDictionaryEntry struct {
	ContractVersion      string    `json:"contract_version"`
	Source               string    `json:"source"`
	Dataset              string    `json:"dataset"`
	LabelZh              string    `json:"label_zh"`
	DataTypes            []string  `json:"data_types"`
	StorageTable         string    `json:"storage_table,omitempty"`
	StorageTablespace    string    `json:"storage_tablespace,omitempty"`
	DictionaryTablespace string    `json:"dictionary_tablespace,omitempty"`
	SourceDoc            string    `json:"source_doc,omitempty"`
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

// FieldDictionaryEntry mirrors a row in data_field_dictionary.
type FieldDictionaryEntry struct {
	ContractVersion string    `json:"contract_version"`
	Source          string    `json:"source"`
	Dataset         string    `json:"dataset"`
	DataType        string    `json:"data_type"`
	DataTypeLabelZh string    `json:"data_type_label_zh,omitempty"`
	SDKSection      string    `json:"sdk_section,omitempty"`
	SDKFunction     string    `json:"sdk_function,omitempty"`
	RawField        string    `json:"raw_field"`
	CanonicalField  string    `json:"canonical_field"`
	LabelZh         string    `json:"label_zh"`
	Description     string    `json:"description,omitempty"`
	ValueType       string    `json:"value_type"`
	SourceValueType string    `json:"source_value_type,omitempty"`
	Unit            string    `json:"unit,omitempty"`
	Scale           *float64  `json:"scale,omitempty"`
	EnumRef         string    `json:"enum_ref,omitempty"`
	StorageLocation string    `json:"storage_location"`
	IsMetadata      bool      `json:"is_metadata"`
	IsCore          bool      `json:"is_core"`
	CompTypeScope   string    `json:"comp_type_scope,omitempty"`
	Aliases         []string  `json:"aliases,omitempty"`
	SourceDoc       string    `json:"source_doc,omitempty"`
	SourcePath      string    `json:"source_path,omitempty"`
	ReviewStatus    string    `json:"review_status,omitempty"`
	Deprecated      bool      `json:"deprecated"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// EnumDictionaryEntry mirrors a row in data_enum_dictionary.
type EnumDictionaryEntry struct {
	ContractVersion string    `json:"contract_version"`
	Source          string    `json:"source"`
	EnumName        string    `json:"enum_name"`
	Code            string    `json:"code"`
	LabelZh         string    `json:"label_zh"`
	Description     string    `json:"description,omitempty"`
	SortOrder       int       `json:"sort_order"`
	SourceDoc       string    `json:"source_doc,omitempty"`
	ReviewStatus    string    `json:"review_status,omitempty"`
	Deprecated      bool      `json:"deprecated"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// ─── Discovery API responses ───

// DatasetDiscoveryResponse is returned by GET /api/v2/catalog/datasets.
type DatasetDiscoveryResponse struct {
	GeneratedAt     time.Time               `json:"generated_at"`
	ContractVersion string                  `json:"contract_version,omitempty"`
	Datasets        []DatasetDiscoveryEntry `json:"datasets"`
}

// DatasetDiscoveryEntry is one dataset in the discovery response. It augments
// the raw dictionary row with the discovery / query URLs so callers do not
// need to construct them themselves.
type DatasetDiscoveryEntry struct {
	Source         string   `json:"source"`
	Dataset        string   `json:"dataset"`
	LabelZh        string   `json:"label_zh"`
	DataTypes      []string `json:"data_types"`
	StorageTable   string   `json:"storage_table,omitempty"`
	SourceDoc      string   `json:"source_doc,omitempty"`
	FieldDiscovery string   `json:"field_discovery"`
	Query          string   `json:"query,omitempty"`
}

// FieldDiscoveryResponse is returned by GET /api/v2/catalog/datasets/{dataset}/fields.
type FieldDiscoveryResponse struct {
	GeneratedAt     time.Time             `json:"generated_at"`
	Dataset         string                `json:"dataset"`
	Source          string                `json:"source"`
	DataType        string                `json:"data_type,omitempty"`
	ContractVersion string                `json:"contract_version,omitempty"`
	Fields          []FieldDiscoveryEntry `json:"fields"`
}

// FieldDiscoveryEntry is the public-facing projection of a field dictionary
// row. It collapses internal bookkeeping fields (id, timestamps, review
// status) and exposes only what external services need to discover and use a
// field.
type FieldDiscoveryEntry struct {
	RawField        string   `json:"raw_field"`
	CanonicalField  string   `json:"canonical_field"`
	LabelZh         string   `json:"label_zh"`
	Description     string   `json:"description,omitempty"`
	ValueType       string   `json:"value_type"`
	Unit            string   `json:"unit,omitempty"`
	Scale           *float64 `json:"scale,omitempty"`
	EnumRef         string   `json:"enum_ref,omitempty"`
	StorageLocation string   `json:"storage_location"`
	QueryName       string   `json:"query_name"`
	IsMetadata      bool     `json:"is_metadata,omitempty"`
	IsCore          bool     `json:"is_core,omitempty"`
	CompTypeScope   string   `json:"comp_type_scope,omitempty"`
	Aliases         []string `json:"aliases,omitempty"`
	SourceDoc       string   `json:"source_doc,omitempty"`
	Deprecated      bool     `json:"deprecated,omitempty"`
}

// EnumDiscoveryResponse is returned by GET /api/v2/catalog/enums/{enum_name}.
type EnumDiscoveryResponse struct {
	GeneratedAt     time.Time            `json:"generated_at"`
	EnumName        string               `json:"enum_name"`
	Source          string               `json:"source"`
	ContractVersion string               `json:"contract_version,omitempty"`
	Values          []EnumDiscoveryEntry `json:"values"`
}

// EnumDiscoveryEntry is the public-facing projection of an enum dictionary row.
type EnumDiscoveryEntry struct {
	Code        string `json:"code"`
	LabelZh     string `json:"label_zh"`
	Description string `json:"description,omitempty"`
	SortOrder   int    `json:"sort_order,omitempty"`
	Deprecated  bool   `json:"deprecated,omitempty"`
}

// DecodeStringArray parses a JSONB array of strings (e.g. aliases, data_types)
// stored as raw bytes from the database into a []string. Returns an empty
// slice for null or invalid input so callers can safely range over it.
func DecodeStringArray(raw []byte) []string {
	if len(raw) == 0 {
		return nil
	}
	var out []string
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil
	}
	return out
}
