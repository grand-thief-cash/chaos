package dao

import "testing"

func TestCanonicalTaxonomyInfo(t *testing.T) {
	tests := []struct {
		name            string
		source          string
		taxonomy        string
		level           uint8
		wantSource      string
		wantTaxonomy    string
		wantCanonicalLv uint8
	}{
		{
			name:            "sw level inferred from taxonomy alias",
			source:          "amazing_data",
			taxonomy:        "sw_l2",
			wantSource:      "sw",
			wantTaxonomy:    "sw",
			wantCanonicalLv: 2,
		},
		{
			name:            "legacy swhy alias canonicalized to sw",
			source:          "amazing_data",
			taxonomy:        "swhy",
			level:           1,
			wantSource:      "sw",
			wantTaxonomy:    "sw",
			wantCanonicalLv: 1,
		},
		{
			name:            "industry taxonomy derives family from source",
			source:          "citics",
			taxonomy:        "industry",
			level:           3,
			wantSource:      "citics",
			wantTaxonomy:    "citics",
			wantCanonicalLv: 3,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotSource, gotTaxonomy, gotLevel := canonicalTaxonomyInfo(tt.source, tt.taxonomy, tt.level)
			if gotSource != tt.wantSource {
				t.Fatalf("canonical source = %q, want %q", gotSource, tt.wantSource)
			}
			if gotTaxonomy != tt.wantTaxonomy {
				t.Fatalf("canonical taxonomy = %q, want %q", gotTaxonomy, tt.wantTaxonomy)
			}
			if gotLevel != tt.wantCanonicalLv {
				t.Fatalf("canonical level = %d, want %d", gotLevel, tt.wantCanonicalLv)
			}
		})
	}
}

func TestDeriveCategoryFlagsSWByAncestor(t *testing.T) {
	bankCode := "801010"
	leaf := &taxonomyCategoryQuery{
		Source:     "amazing_data",
		Taxonomy:   "sw_l2",
		Market:     "zh_a",
		Code:       "801011",
		Name:       "全国性股份制银行",
		Level:      2,
		ParentCode: &bankCode,
	}
	parent := &taxonomyCategoryQuery{
		Source:   "amazing_data",
		Taxonomy: "sw_l2",
		Market:   "zh_a",
		Code:     bankCode,
		Name:     "银行",
		Level:    1,
	}
	categoryMap := map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery{
		{Source: leaf.Source, Taxonomy: leaf.Taxonomy, Market: leaf.Market, Code: leaf.Code}:         leaf,
		{Source: parent.Source, Taxonomy: parent.Taxonomy, Market: parent.Market, Code: parent.Code}: parent,
	}

	flags := deriveCategoryFlags(leaf, categoryMap, nil, "sw")
	if !flags["financial_sector"] {
		t.Fatalf("expected sw banking subtree to be classified as financial sector")
	}
}

func TestDeriveCategoryFlagsCiticsByName(t *testing.T) {
	cat := &taxonomyCategoryQuery{
		Source:   "amazing_data",
		Taxonomy: "citics_l1",
		Market:   "zh_a",
		Code:     "40",
		Name:     "证券Ⅱ",
		Level:    1,
	}
	categoryMap := map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery{
		{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}: cat,
	}

	flags := deriveCategoryFlags(cat, categoryMap, nil, "citics")
	if !flags["financial_sector"] {
		t.Fatalf("expected citics securities category to be classified as financial sector")
	}
}

func TestDeriveCategoryFlagsPrefersStoredAttrsJSON(t *testing.T) {
	attrs := `{"derived_flags":{"financial_sector":false,"regulated":true}}`
	cat := &taxonomyCategoryQuery{
		Source:   "amazing_data",
		Taxonomy: "sw_l1",
		Market:   "zh_a",
		Code:     "801010",
		Name:     "银行",
		Level:    1,
		AttrsJSON: &attrs,
	}
	categoryMap := map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery{
		{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}: cat,
	}

	flags := deriveCategoryFlags(cat, categoryMap, nil, "sw")
	if flags["financial_sector"] {
		t.Fatalf("expected stored financial_sector flag to be preserved")
	}
	if !flags["regulated"] {
		t.Fatalf("expected custom derived flag from attrs_json to be preserved")
	}
}

func TestDeriveCategoryFlagsPrefersPersistedDerivedTableFlags(t *testing.T) {
	attrs := `{"derived_flags":{"financial_sector":true}}`
	cat := &taxonomyCategoryQuery{
		Source:    "amazing_data",
		Taxonomy:  "sw_l1",
		Market:    "zh_a",
		Code:      "801010",
		Name:      "银行",
		Level:     1,
		AttrsJSON: &attrs,
	}
	categoryMap := map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery{
		{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}: cat,
	}
	flags := deriveCategoryFlags(cat, categoryMap, map[string]bool{"financial_sector": false, "regulated": true}, "sw")
	if flags["financial_sector"] {
		t.Fatalf("expected persisted derived table flag to take precedence")
	}
	if !flags["regulated"] {
		t.Fatalf("expected persisted derived flag to be preserved")
	}
}

func TestParseBoolMapJSON(t *testing.T) {
	payload := `{"financial_sector":true,"regulated":false}`
	flags := parseBoolMapJSON(&payload)
	if !flags["financial_sector"] {
		t.Fatalf("expected financial_sector=true")
	}
	if flags["regulated"] {
		t.Fatalf("expected regulated=false")
	}
}

func TestParseTaxonomyLevel(t *testing.T) {
	cases := []struct {
		input string
		want  uint8
	}{
		{input: "sw_l1", want: 1},
		{input: "sw_l3", want: 3},
		{input: "citics_l2", want: 2},
		{input: "industry", want: 0},
		{input: "", want: 0},
	}
	for _, tc := range cases {
		if got := parseTaxonomyLevel(tc.input); got != tc.want {
			t.Fatalf("parseTaxonomyLevel(%q) = %d, want %d", tc.input, got, tc.want)
		}
	}
}
