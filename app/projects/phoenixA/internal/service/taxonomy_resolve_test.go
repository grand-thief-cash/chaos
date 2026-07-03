package service

import (
	"context"
	"errors"
	"testing"
	"time"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestResolveConCode verifies the vendor code SYMBOL.EXCHANGE splitter used to resolve
// a constituent's con_code to a (exchange, symbol) natural key.
func TestResolveConCode(t *testing.T) {
	tests := []struct {
		conCode      string
		wantExchange string
		wantSymbol   string
		wantOk       bool
	}{
		{"688526.SH", "SH", "688526", true},
		{"000001.SZ", "SZ", "000001", true},
		{"430047.BJ", "BJ", "430047", true},
		{"688526.sh", "SH", "688526", true}, // exchange normalized to upper
		{"000001", "", "", false},           // no exchange suffix
		{"", "", "", false},
		{".SH", "", "", false}, // empty symbol part
	}
	for _, tt := range tests {
		ex, sym, ok := resolveConCode(tt.conCode)
		if ok != tt.wantOk || ex != tt.wantExchange || sym != tt.wantSymbol {
			t.Errorf("resolveConCode(%q) = (%q,%q,%v), want (%q,%q,%v)",
				tt.conCode, ex, sym, ok, tt.wantExchange, tt.wantSymbol, tt.wantOk)
		}
	}
}

// TestResolveCacheLookups exercises the in-memory resolve cache against a hand-populated
// map (no DB). Covers the Phase 2 resolve contract: natural key → id, case-insensitive
// exchange, natural-key normalization (trim), and the orphan-reject rule (unknown natural
// key → error, never a silent zero).
func TestResolveCacheLookups(t *testing.T) {
	c := &ResolveCache{
		secByNatural: map[secNaturalKey]uint64{
			{exchange: "SH", assetType: bizConsts.ASSET_TYPE_STOCK, symbol: "688526"}: 100,
			{exchange: "SZ", assetType: bizConsts.ASSET_TYPE_STOCK, symbol: "000001"}: 200,
		},
		secByID: map[uint64]*model.SecurityRegistry{
			100: {ID: 100, Exchange: "SH", Symbol: "688526", AssetType: bizConsts.ASSET_TYPE_STOCK, Market: bizConsts.MARKET_ZH_A},
		},
		catByNatural: map[catNaturalKey]uint64{
			{source: "amazing_data", taxonomy: "swhy", market: "zh_a", indexCode: "801010.SI"}: 7,
			{source: "amazing_data", taxonomy: "swhy", market: "zh_a", indexCode: "801011.SI"}: 8,
		},
		catByID: map[uint64]*model.TaxonomyCategory{
			7: {ID: 7, Source: "amazing_data", Taxonomy: "swhy", Market: "zh_a"},
		},
		loadedAt: time.Now(),
	}
	ctx := context.Background()

	// security resolve via con_code: "688526.SH" → (SH, 688526) → id 100
	id, err := c.resolveConstituentSecurity(ctx, "688526.SH", "688526")
	if err != nil || id != 100 {
		t.Fatalf("resolveConstituentSecurity(688526.SH) = %d, %v; want 100, nil", id, err)
	}

	// exchange case-insensitive
	id, err = c.resolveConstituentSecurity(ctx, "688526.sh", "")
	if err != nil || id != 100 {
		t.Fatalf("resolveConstituentSecurity(688526.sh) = %d, %v; want 100, nil", id, err)
	}

	// unknown security → error (no silent orphan id)
	if _, err = c.resolveConstituentSecurity(ctx, "999999.SH", ""); err == nil {
		t.Fatal("expected error for unknown con_code, got nil")
	}

	// bare symbol without exchange → error (cannot resolve without exchange)
	if _, err = c.resolveConstituentSecurity(ctx, "", "688526"); err == nil {
		t.Fatal("expected error for bare symbol without exchange, got nil")
	}

	// category resolve — natural key with surrounding whitespace still matches (normalized).
	catID, ok, err := c.ResolveCategoryID(ctx, "amazing_data", "swhy", "zh_a", "801010.SI")
	if err != nil || !ok || catID != 7 {
		t.Fatalf("ResolveCategoryID = %d, %v, %v; want 7, true, nil", catID, ok, err)
	}
	catID, ok, err = c.ResolveCategoryID(ctx, "  amazing_data ", " swhy", " zh_a ", "  801010.SI ")
	if err != nil || !ok || catID != 7 {
		t.Fatalf("ResolveCategoryID with whitespace = %d, %v, %v; want 7, true, nil (normalized)", catID, ok, err)
	}
	if _, ok, err := c.ResolveCategoryID(ctx, "amazing_data", "swhy", "zh_a", "UNKNOWN.SI"); err != nil || ok {
		t.Fatal("ResolveCategoryID should miss (false, nil) for unknown index_code")
	}

	// existence checks (orphan defense for direct mapping writes)
	if found, err := c.SecurityExists(ctx, 100); err != nil || !found {
		t.Errorf("SecurityExists(100) = %v, %v; want true, nil", found, err)
	}
	if found, err := c.SecurityExists(ctx, 999); err != nil || found {
		t.Errorf("SecurityExists(999) = %v, %v; want false, nil", found, err)
	}
	if found, err := c.SecurityExists(ctx, 0); err != nil || found {
		t.Errorf("SecurityExists(0) = %v, %v; want false, nil (zero id short-circuit)", found, err)
	}
	if found, err := c.CategoryExists(ctx, 7); err != nil || !found {
		t.Errorf("CategoryExists(7) = %v, %v; want true, nil", found, err)
	}
	if found, err := c.CategoryExists(ctx, 999); err != nil || found {
		t.Errorf("CategoryExists(999) = %v, %v; want false, nil", found, err)
	}

	// scope resolution: (source, taxonomy, market) → category_id set
	ids, err := c.CategoryIDsForScope(ctx, "amazing_data", "swhy", "zh_a")
	if err != nil || len(ids) != 2 {
		t.Fatalf("CategoryIDsForScope = %v, %v; want 2 ids, nil", ids, err)
	}

	// reverse resolve for display enrichment
	sec, ok, err := c.ResolveSecurity(ctx, 100)
	if err != nil || !ok || sec.Symbol != "688526" {
		t.Fatalf("ResolveSecurity(100) = %+v, %v, %v; want Symbol=688526", sec, ok, err)
	}
}

// TestResolveCacheInvalidateForcesReload verifies Invalidate clears the freshness marker
// so the next access reloads (re-fetches from the DAOs).
func TestResolveCacheInvalidateForcesReload(t *testing.T) {
	c := &ResolveCache{
		secByNatural: map[secNaturalKey]uint64{},
		secByID:      map[uint64]*model.SecurityRegistry{},
		catByNatural: map[catNaturalKey]uint64{},
		catByID:      map[uint64]*model.TaxonomyCategory{},
		loadedAt:     time.Now(),
	}
	c.Invalidate()
	if !c.loadedAt.IsZero() {
		t.Fatalf("Invalidate should reset loadedAt to zero value")
	}
	// ensureLoaded now wants to reload; with nil DAOs reload returns an error (no panic).
	if err := c.ensureLoaded(context.Background()); err == nil {
		t.Fatal("ensureLoaded after Invalidate should error with nil DAOs, not succeed silently")
	}
	// CategoryIDsForScope must surface the load failure as an error (not a silent 0 rows).
	if _, err := c.CategoryIDsForScope(context.Background(), "amazing_data", "swhy", "zh_a"); err == nil {
		t.Fatal("CategoryIDsForScope should error when the cache cannot load, not return empty ok")
	}
}

// TestResolveCacheLoadFailureReturnsError verifies that when the cache cannot load (DB/DAO
// failure), the resolver / exists methods return an error — NOT a silent false that callers
// would misreport as "not found" (→ 400). A load failure is an internal error (→ 500).
// This is the round-3 review fix: distinguish cache/DB failure from a genuine miss.
func TestResolveCacheLoadFailureReturnsError(t *testing.T) {
	c := &ResolveCache{
		secByNatural: map[secNaturalKey]uint64{},
		secByID:      map[uint64]*model.SecurityRegistry{},
		catByNatural: map[catNaturalKey]uint64{},
		catByID:      map[uint64]*model.TaxonomyCategory{},
		loadedAt:     time.Now(),
	}
	c.Invalidate() // forces reload → nil DAOs → error
	ctx := context.Background()

	if _, _, err := c.ResolveSecurityID(ctx, "SH", "stock", "688526"); err == nil {
		t.Error("ResolveSecurityID should return error on cache load failure, not (0,false)")
	}
	if _, _, err := c.ResolveCategoryID(ctx, "amazing_data", "swhy", "zh_a", "801010.SI"); err == nil {
		t.Error("ResolveCategoryID should return error on cache load failure, not (0,false)")
	}
	if _, err := c.SecurityExists(ctx, 100); err == nil {
		t.Error("SecurityExists should return error on cache load failure, not false")
	}
	if _, err := c.CategoryExists(ctx, 7); err == nil {
		t.Error("CategoryExists should return error on cache load failure, not false")
	}

	// resolveConstituentSecurity: a load failure must be a plain error (→ 500), NOT a
	// ValidationError (→ 400). The con_code is valid format, so the only failure is load.
	_, err := c.resolveConstituentSecurity(ctx, "688526.SH", "688526")
	if err == nil {
		t.Fatal("resolveConstituentSecurity should error on cache load failure")
	}
	var ve *ValidationError
	if errors.As(err, &ve) {
		t.Fatalf("resolveConstituentSecurity load failure must NOT be a ValidationError (→400); got %T: %v", err, err)
	}

	// Contrast: a genuinely bad con_code format IS a ValidationError (→ 400) even with a
	// loaded cache — but here the cache is broken, so format-check happens first only if
	// conCode is non-empty and resolveConCode fails. Test that path returns ValidationError.
	c2 := &ResolveCache{
		secByNatural: map[secNaturalKey]uint64{},
		secByID:      map[uint64]*model.SecurityRegistry{},
		catByNatural: map[catNaturalKey]uint64{},
		catByID:      map[uint64]*model.TaxonomyCategory{},
		loadedAt:     time.Now(),
	}
	c2.Invalidate()
	_, err = c2.resolveConstituentSecurity(ctx, "not-a-code", "")
	if err == nil {
		t.Fatal("resolveConstituentSecurity with malformed con_code should error")
	}
	if !errors.As(err, &ve) {
		t.Fatalf("malformed con_code should be a ValidationError (→400); got %T", err)
	}
}
