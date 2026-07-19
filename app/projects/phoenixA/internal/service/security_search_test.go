package service

import (
	"testing"
	"time"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// sampleSecurities is a small registry slice used across the search tests.
// Filter functions are scope-agnostic (the snapshot is already scoped), so a
// mixed list is fine for exercising q / legacy filters and sort.
func sampleSecurities() []*model.SecurityRegistry {
	return []*model.SecurityRegistry{
		{ID: 1, Symbol: "000001", Name: "平安银行", Exchange: "SZ", AssetType: "stock", Market: "zh_a", Status: "active"},
		{ID: 2, Symbol: "600519", Name: "贵州茅台", Exchange: "SH", AssetType: "stock", Market: "zh_a", Status: "active"},
		{ID: 3, Symbol: "000002", Name: "万科A", Exchange: "SZ", AssetType: "stock", Market: "zh_a", Status: "delisted"},
		{ID: 4, Symbol: "AAPL", Name: "Apple Inc", Exchange: "US", AssetType: "stock", Market: "us", Status: "active"},
		{ID: 5, Symbol: "ABC", Name: "FooBar", Exchange: "SZ", AssetType: "stock", Market: "zh_a", Status: "active"},
		{ID: 6, Symbol: "ZZZ", Name: "XABC Y", Exchange: "SH", AssetType: "stock", Market: "zh_a", Status: "active"},
	}
}

func idsOf(list []*model.SecurityRegistry) []uint64 {
	out := make([]uint64, 0, len(list))
	for _, s := range list {
		out = append(out, s.ID)
	}
	return out
}

// ─── q semantics ───

func TestFilterSecurityList_QSymbolExactCaseInsensitive(t *testing.T) {
	got := idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "600519"}))
	if !equalIDs(got, []uint64{2}) {
		t.Fatalf("q=600519 (exact symbol) = %v, want [2]", got)
	}
	// case-insensitive symbol match
	got = idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "aapl"}))
	if !equalIDs(got, []uint64{4}) {
		t.Fatalf("q=aapl (case-insensitive symbol) = %v, want [4]", got)
	}
}

func TestFilterSecurityList_QNameContainsCaseSensitive(t *testing.T) {
	// name contains is case-sensitive: "Apple" matches, "apple" does not.
	got := idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "Apple"}))
	if !equalIDs(got, []uint64{4}) {
		t.Fatalf("q=Apple (name contains, case-sensitive) = %v, want [4]", got)
	}
	got = idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "apple"}))
	// "apple" does NOT match symbol "AAPL" (exact, case-insensitive -> no) and
	// does NOT match name "Apple Inc" (contains, case-sensitive -> no).
	if !equalIDs(got, nil) {
		t.Fatalf("q=apple = %v, want [] (symbol not exact, name case mismatch)", got)
	}
	got = idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "茅台"}))
	if !equalIDs(got, []uint64{2}) {
		t.Fatalf("q=茅台 (name contains) = %v, want [2]", got)
	}
}

func TestFilterSecurityList_QEitherSuffices(t *testing.T) {
	// q="ABC" hits item 5 by symbol-exact AND item 6 by name-contains.
	got := idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "ABC"}))
	if !equalIDs(got, []uint64{5, 6}) {
		t.Fatalf("q=ABC (symbol exact OR name contains) = %v, want [5 6]", got)
	}
}

func TestFilterSecurityList_QNoSymbolPrefixMatching(t *testing.T) {
	// "0000" is a prefix of "000001"/"000002" but NOT an exact match, and no
	// name contains it -> empty. Symbol matching is exact-only by design.
	got := idsOf(filterSecurityList(sampleSecurities(), &model.SecurityFilters{Q: "0000"}))
	if !equalIDs(got, nil) {
		t.Fatalf("q=0000 (no prefix match) = %v, want []", got)
	}
}

func TestFilterSecurityList_QWildcardCharsAreLiterals(t *testing.T) {
	list := []*model.SecurityRegistry{
		{ID: 10, Symbol: "900001", Name: "A_B", Exchange: "SZ"},
		{ID: 11, Symbol: "900002", Name: "AxB", Exchange: "SZ"},
	}
	// "_" is a literal, not a LIKE single-char wildcard: "A_B" matches "A_B"
	// only, not "AxB".
	got := idsOf(filterSecurityList(list, &model.SecurityFilters{Q: "A_B"}))
	if !equalIDs(got, []uint64{10}) {
		t.Fatalf("q=A_B (_ literal) = %v, want [10]", got)
	}
	// "%" is a literal too.
	list2 := []*model.SecurityRegistry{{ID: 20, Symbol: "P1", Name: "50%OFF"}}
	got = idsOf(filterSecurityList(list2, &model.SecurityFilters{Q: "50%OFF"}))
	if !equalIDs(got, []uint64{20}) {
		t.Fatalf("q=50%%OFF (%% literal) = %v, want [20]", got)
	}
	got = idsOf(filterSecurityList(list2, &model.SecurityFilters{Q: "50OFF"}))
	if !equalIDs(got, nil) {
		t.Fatalf("q=50OFF = %v, want [] (%% is literal, not a wildcard)", got)
	}
}

// ─── legacy filters ───

func TestFilterSecurityList_LegacyFilters(t *testing.T) {
	src := sampleSecurities()
	if got := idsOf(filterSecurityList(src, &model.SecurityFilters{Exchange: "sz"})); !equalIDs(got, []uint64{1, 3, 5}) {
		t.Fatalf("exchange=sz (uppercased) = %v, want [1 3 5]", got)
	}
	if got := idsOf(filterSecurityList(src, &model.SecurityFilters{Status: "delisted"})); !equalIDs(got, []uint64{3}) {
		t.Fatalf("status=delisted = %v, want [3]", got)
	}
	if got := idsOf(filterSecurityList(src, &model.SecurityFilters{Symbol: "600519"})); !equalIDs(got, []uint64{2}) {
		t.Fatalf("symbol=600519 (exact) = %v, want [2]", got)
	}
	if got := idsOf(filterSecurityList(src, &model.SecurityFilters{Name: "茅台"})); !equalIDs(got, []uint64{2}) {
		t.Fatalf("name=茅台 (contains) = %v, want [2]", got)
	}
	// status defaults to none -> delisted securities remain queryable.
	if n := len(filterSecurityList(src, &model.SecurityFilters{})); n != len(src) {
		t.Fatalf("empty filter = %d items, want %d (no active-only default)", n, len(src))
	}
}

func TestFilterSecurityList_DoesNotMutateInput(t *testing.T) {
	src := sampleSecurities()
	original := make([]*model.SecurityRegistry, len(src))
	copy(original, src)
	_ = filterSecurityList(src, &model.SecurityFilters{Q: "ABC"})
	for i := range src {
		if src[i] != original[i] {
			t.Fatalf("filterSecurityList mutated the input slice order")
		}
	}
}

// ─── sort + total + pagination (searchOverSnapshot) ───

func TestSearchOverSnapshot_ExactSymbolTierFirst(t *testing.T) {
	// q="ABC": item 5 exact-symbol, item 6 name-fuzzy. Exact must sort first.
	page, total := searchOverSnapshot(sampleSecurities(), &model.SecurityFilters{Q: "ABC"}, 10, 0)
	if total != 2 {
		t.Fatalf("total = %d, want 2", total)
	}
	if len(page) != 2 || page[0].ID != 5 || page[1].ID != 6 {
		got := idsOf(page)
		t.Fatalf("order = %v, want [5 6] (exact-symbol tier first)", got)
	}
}

func TestSearchOverSnapshot_EmptyQIsSymbolASC(t *testing.T) {
	// No Q -> plain symbol ASC (the DAO default order), total = full list.
	page, total := searchOverSnapshot(sampleSecurities(), nil, 10, 0)
	if total != int64(len(sampleSecurities())) {
		t.Fatalf("total = %d, want %d", total, len(sampleSecurities()))
	}
	// symbols ascending: 000001, 000002, 600519, AAPL, ABC, ZZZ
	want := []uint64{1, 3, 2, 4, 5, 6}
	if !equalIDs(idsOf(page), want) {
		t.Fatalf("empty-Q order = %v, want %v (symbol ASC)", idsOf(page), want)
	}
}

func TestSearchOverSnapshot_PaginationTotalConsistency(t *testing.T) {
	src := sampleSecurities()
	// total reflects ALL matches (pre-pagination); page reflects limit/offset
	// over the SORTED list, so list and count can't diverge.
	page, total := searchOverSnapshot(src, nil, 2, 0)
	if total != int64(len(src)) {
		t.Fatalf("total = %d, want %d", total, len(src))
	}
	if len(page) != 2 || page[0].ID != 1 || page[1].ID != 3 {
		t.Fatalf("page 1 = %v, want [1 3] (first 2 by symbol ASC)", idsOf(page))
	}
	page2, _ := searchOverSnapshot(src, nil, 2, 2)
	if len(page2) != 2 || page2[0].ID != 2 || page2[1].ID != 4 {
		t.Fatalf("page 2 = %v, want [2 4] (offset 2)", idsOf(page2))
	}
	// offset past the end -> empty page, total unchanged.
	empty, total2 := searchOverSnapshot(src, nil, 2, 100)
	if len(empty) != 0 || total2 != int64(len(src)) {
		t.Fatalf("offset past end = %d items / total %d, want 0 / %d", len(empty), total2, len(src))
	}
	// limit==0 -> all matches (no pagination).
	all, _ := searchOverSnapshot(src, nil, 0, 0)
	if len(all) != len(src) {
		t.Fatalf("limit=0 = %d items, want %d (no pagination)", len(all), len(src))
	}
}

// ─── snapshot freshness / scope ───

func TestSecuritySnapshot_Fresh(t *testing.T) {
	if (&securitySnapshot{}).fresh() {
		t.Fatalf("zero-value snapshot must not be fresh")
	}
	var nilSnap *securitySnapshot
	if nilSnap.fresh() {
		t.Fatalf("nil snapshot must not be fresh")
	}
	fresh := &securitySnapshot{list: nil, loadedAt: time.Now()}
	if !fresh.fresh() {
		t.Fatalf("just-loaded snapshot must be fresh")
	}
	stale := &securitySnapshot{list: nil, loadedAt: time.Now().Add(-2 * securitySnapshotTTL)}
	if stale.fresh() {
		t.Fatalf("snapshot older than TTL must not be fresh")
	}
}

func TestScopeKey_DefaultsToStockZhA(t *testing.T) {
	if got := scopeKey("", ""); got != "stock:zh_a" {
		t.Fatalf("scopeKey('','') = %q, want stock:zh_a", got)
	}
	if got := scopeKey(bizConsts.ASSET_TYPE_STOCK, bizConsts.MARKET_ZH_A); got != "stock:zh_a" {
		t.Fatalf("scopeKey(stock,zh_a) = %q, want stock:zh_a", got)
	}
}

// TestSecurityService_InvalidateL1ClearsSnapshot verifies that a registry
// mutation clears the process-local L1 - the local half of the invalidation
// (the cross-replica half is TTL-bounded). Constructed directly so no DB is
// needed; loadSnapshot itself is exercised by the integration path.
func TestSecurityService_InvalidateL1ClearsSnapshot(t *testing.T) {
	s := NewSecurityService()
	s.l1["stock:zh_a"] = &securitySnapshot{list: nil, loadedAt: time.Now()}
	if len(s.l1) != 1 {
		t.Fatalf("setup: expected 1 L1 entry, got %d", len(s.l1))
	}
	s.invalidateL1()
	if len(s.l1) != 0 {
		t.Fatalf("invalidateL1 left %d entries, want 0", len(s.l1))
	}
}

func equalIDs(a []uint64, b []uint64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
