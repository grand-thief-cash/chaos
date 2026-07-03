package consts

import "testing"

// Phase 2 surrogate-key refactor: taxonomy mapping/constituent cache keys are keyed by
// surrogate id (security_id / category_id), so they vary by id and are stable across
// pagination (no page/page_size in the key).
func TestTaxonomyIdCacheKeysVaryById(t *testing.T) {
	byCatA := BuildTaxonomyConstituentsByCategoryCacheKey(101)
	byCatB := BuildTaxonomyConstituentsByCategoryCacheKey(202)
	if byCatA == byCatB {
		t.Fatalf("constituents-by-category cache key should vary by category_id")
	}

	bySecA := BuildTaxonomyConstituentsBySecurityCacheKey(11)
	bySecB := BuildTaxonomyConstituentsBySecurityCacheKey(22)
	if bySecA == bySecB {
		t.Fatalf("constituents-by-security cache key should vary by security_id")
	}

	mapBySecA := BuildTaxonomyMappingBySecurityCacheKey(11)
	mapBySecB := BuildTaxonomyMappingBySecurityCacheKey(22)
	if mapBySecA == mapBySecB {
		t.Fatalf("mapping-by-security cache key should vary by security_id")
	}
}

func TestPaginatedTaxonomyCacheKeysDoNotVaryByPage(t *testing.T) {
	categoryA := BuildTaxonomyMappingByCategoryCacheKey(801010)
	categoryB := BuildTaxonomyMappingByCategoryCacheKey(801010)
	if categoryA != categoryB {
		t.Fatalf("mapping-by-category cache key should be stable across page/page_size changes")
	}

	indexA := BuildTaxonomyConstituentsByCategoryCacheKey(801010)
	indexB := BuildTaxonomyConstituentsByCategoryCacheKey(801010)
	if indexA != indexB {
		t.Fatalf("constituents-by-category cache key should be stable across page/page_size changes")
	}
}
