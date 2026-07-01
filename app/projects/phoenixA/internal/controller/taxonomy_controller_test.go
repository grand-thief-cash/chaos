package controller

import (
	"encoding/json"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestIndustryWeightJSONDeserialization verifies Artemis payload can be
// correctly deserialized into IndustryWeight model, including trade_date normalization.
func TestIndustryWeightJSONDeserialization(t *testing.T) {
	artemisPayload := `[{
		"index_code": "851426.SI",
		"con_code": "000001.SZ",
		"symbol": "000001",
		"trade_date": "2026-05-07",
		"weight": 0.0523
	}]`

	var list []*model.IndustryWeight
	if err := json.Unmarshal([]byte(artemisPayload), &list); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(list))
	}
	w := list[0]
	if w.IndexCode != "851426.SI" {
		t.Errorf("expected index_code=851426.SI, got %s", w.IndexCode)
	}
	if w.ConCode != "000001.SZ" {
		t.Errorf("expected con_code=000001.SZ, got %s", w.ConCode)
	}
	if w.Symbol != "000001" {
		t.Errorf("expected symbol=000001, got %s", w.Symbol)
	}
	if w.TradeDate != "2026-05-07" {
		t.Errorf("expected trade_date=2026-05-07, got %s", w.TradeDate)
	}
	if w.Weight != 0.0523 {
		t.Errorf("expected weight=0.0523, got %f", w.Weight)
	}
}

// TestIndustryWeightYYYYMMDDNormalization verifies that raw SDK date format (YYYYMMDD)
// gets normalized to YYYY-MM-DD.
func TestIndustryWeightYYYYMMDDNormalization(t *testing.T) {
	rawPayload := `[{
		"index_code": "801010.SI",
		"con_code": "600519.SH",
		"symbol": "600519",
		"trade_date": "20260507",
		"weight": 1.23
	}]`

	var list []*model.IndustryWeight
	if err := json.Unmarshal([]byte(rawPayload), &list); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	w := list[0]
	// The raw YYYYMMDD format should be normalized by the controller
	result := normalizeDateYYYYMMDD(w.TradeDate)
	if result != "2026-05-07" {
		t.Errorf("normalizeDateYYYYMMDD('20260507') = %q, want '2026-05-07'", result)
	}
}

// TestIndustryDailyJSONDeserialization verifies Artemis payload for daily data.
func TestIndustryDailyJSONDeserialization(t *testing.T) {
	artemisPayload := `[{
		"index_code": "851783.SI",
		"trade_date": "2026-05-07",
		"open": 3200.5,
		"high": 3250.0,
		"close": 3230.2,
		"low": 3190.0,
		"pre_close": 3195.0,
		"amount": 123456789.0,
		"volume": 9876543.0,
		"pb": 1.23,
		"pe": 15.6,
		"total_cap": 500000000000.0,
		"a_float_cap": 200000000000.0
	}]`

	var list []*model.IndustryDaily
	if err := json.Unmarshal([]byte(artemisPayload), &list); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(list))
	}
	d := list[0]
	if d.IndexCode != "851783.SI" {
		t.Errorf("expected index_code=851783.SI, got %s", d.IndexCode)
	}
	if d.TradeDate != "2026-05-07" {
		t.Errorf("expected trade_date=2026-05-07, got %s", d.TradeDate)
	}
	if d.Open != 3200.5 {
		t.Errorf("expected open=3200.5, got %f", d.Open)
	}
	if d.PE != 15.6 {
		t.Errorf("expected pe=15.6, got %f", d.PE)
	}
}

// TestIndustryConstituentJSONDeserialization verifies constituent payload.
func TestIndustryConstituentJSONDeserialization(t *testing.T) {
	artemisPayload := `[{
		"index_code": "801010.SI",
		"con_code": "688526.SH",
		"symbol": "688526",
		"in_date": "20220101",
		"out_date": "",
		"index_name": "银行I"
	}]`

	var list []*model.IndustryConstituent
	if err := json.Unmarshal([]byte(artemisPayload), &list); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(list))
	}
	c := list[0]
	if c.IndexCode != "801010.SI" {
		t.Errorf("expected index_code=801010.SI, got %s", c.IndexCode)
	}
	if c.ConCode != "688526.SH" {
		t.Errorf("expected con_code=688526.SH, got %s", c.ConCode)
	}
	if c.Symbol != "688526" {
		t.Errorf("expected symbol=688526, got %s", c.Symbol)
	}
	if c.IndexName != "银行I" {
		t.Errorf("expected index_name=银行I, got %s", c.IndexName)
	}
	if c.InDate == nil || *c.InDate != "20220101" {
		t.Errorf("expected in_date=20220101, got %v", c.InDate)
	}
	if c.OutDate != nil && *c.OutDate != "" {
		t.Errorf("expected out_date empty, got %q", *c.OutDate)
	}
}

// TestNormalizeDateYYYYMMDD tests the date normalization helper.
func TestNormalizeDateYYYYMMDD(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"20260507", "2026-05-07"},
		{"2026-05-07", "2026-05-07"},
		{"2026-01-05T00:00:00+08:00", "2026-01-05"},
		{"", ""},
	}
	for _, tt := range tests {
		result := normalizeDateYYYYMMDD(tt.input)
		if result != tt.expected {
			t.Errorf("normalizeDateYYYYMMDD(%q) = %q, want %q", tt.input, result, tt.expected)
		}
	}
}

// TestTaxonomyCategoryJSONDeserialization verifies category payload with parent_code.
func TestTaxonomyCategoryJSONDeserialization(t *testing.T) {
	artemisPayload := `[{
		"code": "42",
		"name": "银行业",
		"parent_code": null,
		"index_code": "801010.SI",
		"level": 1,
		"is_leaf": false
	}, {
		"code": "4208",
		"name": "银行II",
		"parent_code": "42",
		"index_code": "851426.SI",
		"level": 2,
		"is_leaf": false
	}, {
		"code": "420803",
		"name": "银行III",
		"parent_code": "4208",
		"index_code": "851783.SI",
		"level": 3,
		"is_leaf": true
	}]`

	var list []*model.TaxonomyCategory
	if err := json.Unmarshal([]byte(artemisPayload), &list); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(list) != 3 {
		t.Fatalf("expected 3 entries, got %d", len(list))
	}

	// Level 1 — no parent
	if list[0].ParentCode != nil {
		t.Errorf("level-1 parent_code should be nil, got %v", list[0].ParentCode)
	}
	// Level 2 — parent is level-1 code
	if *list[1].ParentCode != "42" {
		t.Errorf("level-2 parent_code should be '42', got %s", *list[1].ParentCode)
	}
	// Level 3 — parent is level-2 code
	if *list[2].ParentCode != "4208" {
		t.Errorf("level-3 parent_code should be '4208', got %s", *list[2].ParentCode)
	}
}

func TestTaxonomySecurityMapWithDetailJSONSerialization(t *testing.T) {
	payload := &model.TaxonomySecurityMapWithDetail{
		ID:                    1,
		Source:                "amazing_data",
		Taxonomy:              "sw_l1",
		CategoryCode:          "801010",
		CategoryName:          "银行",
		Level:                 1,
		ParentCode:            "",
		IndexCode:             "801010.SI",
		CanonicalSource:       "sw",
		CanonicalTaxonomy:     "sw",
		CanonicalLevel:        1,
		CanonicalCategoryCode: "801010",
		CanonicalCategoryName: "银行",
		CanonicalParentCode:   "",
		CanonicalIndexCode:    "801010.SI",
		DerivedFlags:          map[string]bool{"financial_sector": true},
		Symbol:                "000001",
		AssetType:             "stock",
		Market:                "zh_a",
	}

	b, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var data map[string]any
	if err := json.Unmarshal(b, &data); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	for _, field := range []string{
		"index_code",
		"canonical_source",
		"canonical_taxonomy",
		"canonical_level",
		"canonical_category_code",
		"canonical_category_name",
		"canonical_parent_code",
		"canonical_index_code",
		"derived_flags",
	} {
		if _, ok := data[field]; !ok {
			t.Fatalf("expected field %q to be present in JSON", field)
		}
	}

	if got := data["canonical_source"]; got != "sw" {
		t.Fatalf("canonical_source = %v, want sw", got)
	}
	flags, ok := data["derived_flags"].(map[string]any)
	if !ok {
		t.Fatalf("derived_flags = %T, want object", data["derived_flags"])
	}
	if got := flags["financial_sector"]; got != true {
		t.Fatalf("derived_flags.financial_sector = %v, want true", got)
	}
}
