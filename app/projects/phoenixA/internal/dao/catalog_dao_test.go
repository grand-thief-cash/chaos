package dao

import (
	"testing"
)

func TestHumanSize(t *testing.T) {
	cases := []struct {
		bytes    int64
		expected string
	}{
		{0, "0 B"},
		{512, "512 B"},
		{1024, "1.0 KB"},
		{1536, "1.5 KB"},
		{1048576, "1.0 MB"},
		{1073741824, "1.0 GB"},
		{3435973837, "3.2 GB"},    // ~3.2 GB
		{1099511627776, "1.0 TB"}, // 1 TB
		{2199023255552, "2.0 TB"}, // 2 TB
	}

	for _, c := range cases {
		got := HumanSize(c.bytes)
		if got != c.expected {
			t.Errorf("HumanSize(%d) = %q, want %q", c.bytes, got, c.expected)
		}
	}
}

func TestSafeIdentifierRe(t *testing.T) {
	valid := []string{
		"trade_date",
		"symbol",
		"public",
		"kg",
		"bars_stock_zh_a_daily_nf",
		"_internal",
		"A123",
	}
	for _, id := range valid {
		if !SafeIdentifierRe.MatchString(id) {
			t.Errorf("expected %q to be a safe identifier", id)
		}
	}

	invalid := []string{
		"Robert'; DROP TABLE students;--",
		"foo bar",
		"1_starts_with_number",
		"table-name",
		"",
		"foo()",
		"foo;bar",
		"schema.table",
	}
	for _, id := range invalid {
		if SafeIdentifierRe.MatchString(id) {
			t.Errorf("expected %q to be rejected as unsafe identifier", id)
		}
	}
}

func TestBarsTableName(t *testing.T) {
	got := BarsTableName("stock", "zh_a", "daily", "nf")
	want := "ods.bars_stock_zh_a_daily_nf"
	if got != want {
		t.Errorf("BarsTableName: got %q, want %q", got, want)
	}
}

func TestBarsExtTableName(t *testing.T) {
	got := BarsExtTableName("baostock", "stock", "zh_a", "daily")
	want := "ods.bars_ext_baostock_stock_zh_a_daily"
	if got != want {
		t.Errorf("BarsExtTableName: got %q, want %q", got, want)
	}
}
