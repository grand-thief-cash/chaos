package dao

import (
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestBuildResolvedFieldSecurityID verifies the synthetic security_id top-level
// field (Phase 3) resolves to the real `security_id` column. This is the
// field-dictionary behavior behind `fields=security_id` on the financial /
// corporate-action / equity-structure query APIs.
func TestBuildResolvedFieldSecurityID(t *testing.T) {
	entry := model.FieldDictionaryEntry{
		Source:          "amazing_data",
		Dataset:         "financial_statement",
		DataType:        "balance_sheet",
		RawField:        "security_id",
		CanonicalField:  "security_id",
		LabelZh:         "证券ID",
		ValueType:       "integer",
		StorageLocation: "top_level",
		IsMetadata:      true,
		Aliases:         []string{},
	}

	rf := buildResolvedField(entry)

	if rf.SelectExpr != "security_id" {
		t.Errorf("SelectExpr: got %q, want %q (must be the real column, not a data_json projection)", rf.SelectExpr, "security_id")
	}
	if rf.OutputKey != "security_id" {
		t.Errorf("OutputKey: got %q, want %q", rf.OutputKey, "security_id")
	}
	if rf.ValueType != "integer" {
		t.Errorf("ValueType: got %q, want %q", rf.ValueType, "integer")
	}
	if rf.StorageLocation != "top_level" {
		t.Errorf("StorageLocation: got %q, want %q", rf.StorageLocation, "top_level")
	}
}

// TestBuildResolvedFieldSecurityIDNoLegacyAlias confirms the security_id row
// carries no symbol/MARKET_CODE alias: a legacy `fields=symbol` or
// `fields=MARKET_CODE` request must NOT resolve to security_id (it must return
// 400 unknown field). The seed generator sets aliases=[] for this row; this
// test pins that contract at the resolve layer.
func TestBuildResolvedFieldSecurityIDNoLegacyAlias(t *testing.T) {
	entry := model.FieldDictionaryEntry{
		RawField:        "security_id",
		CanonicalField:  "security_id",
		ValueType:       "integer",
		StorageLocation: "top_level",
		Aliases:         []string{},
	}
	rf := buildResolvedField(entry)
	// The resolved field must not advertise symbol/MARKET_CODE as an alias.
	for _, a := range entry.Aliases {
		if a == "symbol" || a == "MARKET_CODE" {
			t.Errorf("security_id row must not alias legacy %q (would let fields=%s resolve to security_id instead of 400)", a, a)
		}
	}
	// SelectExpr remains the real column regardless.
	if rf.SelectExpr != "security_id" {
		t.Errorf("SelectExpr: got %q, want security_id", rf.SelectExpr)
	}
}
