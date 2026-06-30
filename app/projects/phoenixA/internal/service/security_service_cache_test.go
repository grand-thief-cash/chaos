package service

import (
	"testing"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestSecurityAggregateCacheScope_DefaultFullListIsCacheable(t *testing.T) {
	assetType, market, ok := securityAggregateCacheScope(nil, 0, 0)
	if !ok {
		t.Fatalf("expected default full list to be cacheable")
	}
	if assetType != bizConsts.ASSET_TYPE_STOCK || market != bizConsts.MARKET_ZH_A {
		t.Fatalf("unexpected scope: %s/%s", assetType, market)
	}
}

func TestSecurityAggregateCacheScope_FilteredQueryIsNotCacheable(t *testing.T) {
	_, _, ok := securityAggregateCacheScope(&model.SecurityFilters{Name: "平安"}, 0, 0)
	if ok {
		t.Fatalf("expected name-filtered query to be non-cacheable")
	}
}

func TestSecurityAggregateCacheScope_PaginatedQueryIsNotCacheable(t *testing.T) {
	_, _, ok := securityAggregateCacheScope(&model.SecurityFilters{AssetType: bizConsts.ASSET_TYPE_STOCK, Market: bizConsts.MARKET_ZH_A}, 100, 0)
	if ok {
		t.Fatalf("expected paginated query to be non-cacheable")
	}
}
