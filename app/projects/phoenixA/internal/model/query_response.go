package model

import "time"

// ─── Phase 3: dictionary-resolved query response models ───
//
// Shared by financial_statement / corporate_action / equity_structure query
// APIs. Each query API accepts a `fields` parameter (raw or canonical field
// names), resolves each requested field against data_field_dictionary, and
// returns either a flat or nested row representation along with field
// metadata (label/unit/value_type) so callers do not need a second round-trip
// to the discovery API.

// FlatQueryResponse is the format=flat response shape. Each row is a flat
// map keyed by raw_field name; top-level columns and data_json fields are
// merged into the same map. Suitable for pandas / factor engines / BI tools.
type FlatQueryResponse struct {
	GeneratedAt time.Time   `json:"generated_at"`
	Dataset     string      `json:"dataset"`
	Source      string      `json:"source"`
	DataType    string      `json:"data_type,omitempty"`
	Rows        []FlatRow   `json:"rows"`
	Fields      []FieldMeta `json:"fields"`
	Total       int64       `json:"total"`
	Page        int         `json:"page,omitempty"`
	PageSize    int         `json:"page_size,omitempty"`
}

// FlatRow is one flat row. Values are typed (number stays float64, date stays
// string, etc.) — the controller decodes the raw SQL scan into this map.
type FlatRow map[string]any

// FieldMeta describes one projected field in the response. Returned alongside
// the rows so callers can render headers / units without a discovery call.
type FieldMeta struct {
	Name            string   `json:"name"`
	RawField        string   `json:"raw_field,omitempty"`
	CanonicalField  string   `json:"canonical_field,omitempty"`
	LabelZh         string   `json:"label_zh,omitempty"`
	ValueType       string   `json:"value_type,omitempty"`
	Unit            string   `json:"unit,omitempty"`
	Scale           *float64 `json:"scale,omitempty"`
	StorageLocation string   `json:"storage_location,omitempty"`
	IsMetadata      bool     `json:"is_metadata,omitempty"`
	IsCore          bool     `json:"is_core,omitempty"`
}

// NestedQueryResponse is the format=nested response shape. Each row preserves
// the top-level columns plus the raw data_json object, so callers that need
// the original SDK structure get it intact.
type NestedQueryResponse struct {
	GeneratedAt time.Time   `json:"generated_at"`
	Dataset     string      `json:"dataset"`
	Source      string      `json:"source"`
	DataType    string      `json:"data_type,omitempty"`
	Rows        []NestedRow `json:"rows"`
	Total       int64       `json:"total"`
	Page        int         `json:"page,omitempty"`
	PageSize    int         `json:"page_size,omitempty"`
}

// NestedRow is one nested row. TopLevel carries the stable top-level columns
// (symbol, reporting_period, etc.); DataJSON carries the raw SDK payload. When
// `fields` is specified, DataJSON is filtered to just those keys; otherwise it
// is the full object.
type NestedRow struct {
	TopLevel map[string]any `json:"top_level"`
	DataJSON map[string]any `json:"data_json,omitempty"`
}

// FieldResolutionError is returned when one or more requested fields cannot be
// resolved against the field dictionary. It carries per-field suggestions so
// the caller can correct the request without consulting docs. Implements the
// error interface so it can bubble up through service-layer return values.
type FieldResolutionError struct {
	Code     string             `json:"error"` // "unknown_field"
	Dataset  string             `json:"dataset"`
	DataType string             `json:"data_type,omitempty"`
	Source   string             `json:"source,omitempty"`
	Unknown  []UnknownFieldHint `json:"unknown"`
}

// Error implements the error interface. Returns the error code (e.g.
// "unknown_field") so the value satisfies error in service-layer returns.
func (e *FieldResolutionError) Error() string {
	if e.Code == "" {
		return "field resolution error"
	}
	return e.Code
}

// UnknownFieldHint pairs an unresolved field name with suggested fields. The
// suggestions come from the dictionary's aliases plus simple substring /
// edit-distance matches on raw_field and canonical_field.
type UnknownFieldHint struct {
	Field       string            `json:"field"`
	Suggestions []FieldSuggestion `json:"suggestions,omitempty"`
}

// FieldSuggestion is a candidate field for an unknown-field hint.
type FieldSuggestion struct {
	Field    string `json:"field"`
	RawField string `json:"raw_field,omitempty"`
	LabelZh  string `json:"label_zh,omitempty"`
}
