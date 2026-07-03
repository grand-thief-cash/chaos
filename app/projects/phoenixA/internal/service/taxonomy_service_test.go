package service

import (
	"context"
	"errors"
	"testing"
	"time"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// handBuiltService returns a TaxonomyService wired to a hand-populated resolve cache (no DB,
// no Redis). Used to exercise service-level validation / sync paths that fail before the DAO
// is touched, so a nil Dao is safe.
func handBuiltService() *TaxonomyService {
	return &TaxonomyService{
		Resolve: &ResolveCache{
			secByNatural: map[secNaturalKey]uint64{
				{exchange: "SH", assetType: bizConsts.ASSET_TYPE_STOCK, symbol: "688526"}: 100,
			},
			secByID: map[uint64]*model.SecurityRegistry{
				100: {ID: 100, Exchange: "SH", Symbol: "688526", AssetType: bizConsts.ASSET_TYPE_STOCK, Market: bizConsts.MARKET_ZH_A},
			},
			catByNatural: map[catNaturalKey]uint64{
				{source: "amazing_data", taxonomy: "swhy", market: "zh_a", indexCode: "801010.SI"}: 7,
			},
			// catByID intentionally holds a category with NO index_code (id 9) — the base-table
			// identity is (source,taxonomy,market,code), not index_code, so existence checks
			// must still recognize it. reload() must populate catByID for every category.
			catByID: map[uint64]*model.TaxonomyCategory{
				7: {ID: 7, Source: "amazing_data", Taxonomy: "swhy", Market: "zh_a", IndexCode: strPtr("801010.SI")},
				9: {ID: 9, Source: "amazing_data", Taxonomy: "citics", Market: "zh_a", IndexCode: nil},
			},
			loadedAt: time.Now(),
		},
	}
}

func strPtr(s string) *string { return &s }

// TestBatchUpsertMappingsRejectsUnknownID verifies a direct mapping write with a non-existent
// security_id is rejected as a ValidationError (→ 400, not 500) before the DAO is touched.
func TestBatchUpsertMappingsRejectsUnknownID(t *testing.T) {
	svc := handBuiltService()
	ctx := context.Background()

	err := svc.BatchUpsertMappings(ctx, []*model.TaxonomySecurityMap{
		{SecurityID: 999, CategoryID: 7}, // 999 does not exist
	})
	var ve *ValidationError
	if !errors.As(err, &ve) {
		t.Fatalf("BatchUpsertMappings with unknown security_id: got %T %v, want *ValidationError", err, err)
	}
}

// TestBatchUpsertMappingsRejectsUnknownCategoryID covers the category side, including a
// category that has no index_code (id 9 is valid and must be accepted; id 888 is not).
func TestBatchUpsertMappingsRejectsUnknownCategoryID(t *testing.T) {
	svc := handBuiltService()
	ctx := context.Background()

	// id 9 is a valid category (no index_code) — should be accepted on the category axis,
	// but security_id 100 is valid too, so this should succeed at validation (Dao is nil →
	// the subsequent DAO call would panic, so instead test the reject path):
	err := svc.validateMappingIDs(ctx, []uint64{100}, []uint64{9})
	if err != nil {
		t.Fatalf("validateMappingIDs(valid sec=100, cat=9-no-index_code) = %v, want nil (no-index_code category is valid)", err)
	}

	err = svc.validateMappingIDs(ctx, []uint64{100}, []uint64{888})
	var ve *ValidationError
	if !errors.As(err, &ve) {
		t.Fatalf("validateMappingIDs with unknown category_id: got %T %v, want *ValidationError", err, err)
	}
}

// TestCategoryExistsAcceptsNoIndexCode verifies CategoryExists returns true for a category
// without an index_code (catByID holds every category, not just index_code-bearing ones).
func TestCategoryExistsAcceptsNoIndexCode(t *testing.T) {
	c := handBuiltService().Resolve
	ctx := context.Background()
	if found, err := c.CategoryExists(ctx, 9); err != nil || !found {
		t.Fatalf("CategoryExists(9) = %v, %v; want true, nil for a no-index_code category", found, err)
	}
	if found, err := c.CategoryExists(ctx, 7); err != nil || !found {
		t.Fatalf("CategoryExists(7) = %v, %v; want true, nil", found, err)
	}
	if found, err := c.CategoryExists(ctx, 888); err != nil || found {
		t.Fatalf("CategoryExists(888) = %v, %v; want false, nil", found, err)
	}
}

// TestSyncMappingsFromConstituentsEmptyScopeErrors verifies an empty scope (misspelled path
// or taxonomy_category not imported) is surfaced as a ValidationError (→ 400), not a silent
// 0-row success.
func TestSyncMappingsFromConstituentsEmptyScopeErrors(t *testing.T) {
	svc := handBuiltService()
	ctx := context.Background()

	_, err := svc.SyncMappingsFromConstituents(ctx, "amazing_data", "NONEXISTENT_TAXONOMY", "zh_a")
	var ve *ValidationError
	if !errors.As(err, &ve) {
		t.Fatalf("SyncMappingsFromConstituents empty scope: got %T %v, want *ValidationError", err, err)
	}
}

// TestSyncMappingsFromConstituentsCacheLoadError verifies a cache load failure is surfaced
// as an error (not silent 0 rows). Force it by invalidating the cache so reload runs against
// nil DAOs.
func TestSyncMappingsFromConstituentsCacheLoadError(t *testing.T) {
	svc := handBuiltService()
	svc.Resolve.Invalidate() // forces reload on next access → nil DAOs → error
	ctx := context.Background()

	_, err := svc.SyncMappingsFromConstituents(ctx, "amazing_data", "swhy", "zh_a")
	if err == nil {
		t.Fatal("SyncMappingsFromConstituents with unreachable cache should error, not return 0 ok")
	}
	// The cache-load error is a plain error (wrapped), NOT a ValidationError — it's an
	// internal failure, so the controller would map it to 500.
	var ve *ValidationError
	if errors.As(err, &ve) {
		t.Fatalf("cache-load failure should NOT be a ValidationError (internal, 500); got %T", err)
	}
}

// TestConflictErrorType verifies the ConflictError type is recognizable via errors.As
// (DeleteCategory / DeleteAll reference guards return it → controllers map to 409).
func TestConflictErrorType(t *testing.T) {
	err := NewConflictError("referenced by X")
	var ce *ConflictError
	if !errors.As(err, &ce) {
		t.Fatalf("NewConflictError not recognized as *ConflictError")
	}
	// A ValidationError must NOT match ConflictError (distinct status codes).
	ve := NewValidationError("bad id")
	if errors.As(ve, &ce) {
		t.Fatal("ValidationError must not be recognized as ConflictError")
	}
}
