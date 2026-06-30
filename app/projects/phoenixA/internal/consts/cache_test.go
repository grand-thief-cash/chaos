package consts

import "testing"

func TestTaxonomyIndustryCacheKeysIncludeMarket(t *testing.T) {
	byIndexA := BuildTaxonomyConstituentsByIndexCacheKey("amazing_data", "sw_l1", "zh_a", "801010.SI")
	byIndexHK := BuildTaxonomyConstituentsByIndexCacheKey("amazing_data", "sw_l1", "hk", "801010.SI")
	if byIndexA == byIndexHK {
		t.Fatalf("constituents-by-index cache key should vary by market")
	}

	bySymbolA := BuildTaxonomyConstituentsBySymbolCacheKey("amazing_data", "sw_l1", "zh_a", "600519")
	bySymbolHK := BuildTaxonomyConstituentsBySymbolCacheKey("amazing_data", "sw_l1", "hk", "600519")
	if bySymbolA == bySymbolHK {
		t.Fatalf("constituents-by-symbol cache key should vary by market")
	}
}

func TestPaginatedTaxonomyCacheKeysDoNotVaryByPage(t *testing.T) {
	categoryA := BuildTaxonomyMappingByCategoryCacheKey("amazing_data", "sw_l1", "801010")
	categoryB := BuildTaxonomyMappingByCategoryCacheKey("amazing_data", "sw_l1", "801010")
	if categoryA != categoryB {
		t.Fatalf("mapping-by-category cache key should be stable across page/page_size changes")
	}

	indexA := BuildTaxonomyConstituentsByIndexCacheKey("amazing_data", "sw_l1", "zh_a", "801010.SI")
	indexB := BuildTaxonomyConstituentsByIndexCacheKey("amazing_data", "sw_l1", "zh_a", "801010.SI")
	if indexA != indexB {
		t.Fatalf("constituents-by-index cache key should be stable across page/page_size changes")
	}
}
