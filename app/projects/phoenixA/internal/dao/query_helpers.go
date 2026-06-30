package dao

import (
	"fmt"
	"strings"
)

// ─── Phase 3: shared SELECT builders for dictionary-resolved queries ───
//
// These helpers build SELECT expressions from []ResolvedField. They are used
// by financial_statement / corporate_action / equity_structure DAOs so the
// flat/nested projection logic is not triplicated.
//
// All identifiers interpolated into SQL here come from ResolvedField, whose
// values are dictionary-sourced and validated at resolution time. User input
// never reaches these functions directly.

// BuildFlatSelect returns the SELECT list for a flat query plus the ordered
// output keys. Each resolved field becomes one column aliased to its
// OutputKey (double-quoted to preserve case for UPPER_SNAKE raw_field names).
// Returns ("", nil) when resolved is empty — callers should handle that as
// "no projection, SELECT *".
func BuildFlatSelect(resolved []ResolvedField) (string, []string) {
	if len(resolved) == 0 {
		return "", nil
	}
	parts := make([]string, 0, len(resolved))
	keys := make([]string, 0, len(resolved))
	for _, r := range resolved {
		if r.SelectExpr == "" {
			continue
		}
		alias := r.OutputKey
		if !SafeIdentifierRe.MatchString(alias) {
			// OutputKey should always be a clean identifier (canonical_field
			// or raw_field). Skip if somehow invalid rather than risk SQL.
			continue
		}
		parts = append(parts, fmt.Sprintf("%s AS \"%s\"", r.SelectExpr, alias))
		keys = append(keys, alias)
	}
	if len(parts) == 0 {
		return "", nil
	}
	return strings.Join(parts, ", "), keys
}

// SplitResolved partitions resolved fields into top_level vs data_json slices.
// Used by nested queries: top_level fields go into the row's TopLevel map,
// data_json fields go into the filtered DataJSON object.
func SplitResolved(resolved []ResolvedField) (topLevel, dataJSON []ResolvedField) {
	for _, r := range resolved {
		switch r.StorageLocation {
		case "top_level":
			topLevel = append(topLevel, r)
		case "data_json":
			dataJSON = append(dataJSON, r)
		}
	}
	return
}

// BuildFilteredDataJSON returns a SQL expression that builds a JSONB object
// containing only the requested data_json keys. Returns "" when no data_json
// fields are requested, so callers can fall back to selecting the full
// data_json column.
//
// Example output:
//
//	jsonb_build_object('TOTAL_ASSETS', data_json->'TOTAL_ASSETS',
//	                   'TOTAL_LIAB',   data_json->'TOTAL_LIAB') AS data_json
func BuildFilteredDataJSON(dataJSONFields []ResolvedField) string {
	if len(dataJSONFields) == 0 {
		return ""
	}
	parts := make([]string, 0, len(dataJSONFields)*2)
	for _, r := range dataJSONFields {
		if !jsonbKeyRe.MatchString(r.RawField) {
			continue
		}
		parts = append(parts, fmt.Sprintf("'%s'", r.RawField), fmt.Sprintf("data_json->'%s'", r.RawField))
	}
	if len(parts) == 0 {
		return ""
	}
	return fmt.Sprintf("jsonb_build_object(%s) AS data_json", strings.Join(parts, ", "))
}
