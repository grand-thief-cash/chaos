package dao

import "testing"

func TestBarsTableNameCanonicalizesMinuteAlias(t *testing.T) {
	got := BarsTableName("stock", "zh_a", "5min", "nf")
	want := "ods.bars_stock_zh_a_min5_nf"
	if got != want {
		t.Fatalf("BarsTableName() = %q, want %q", got, want)
	}
}
