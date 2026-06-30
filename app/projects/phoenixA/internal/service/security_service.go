package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	infraRedis "github.com/grand-thief-cash/chaos/app/infra/go/application/components/redis"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/cache"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	redislib "github.com/redis/go-redis/v9"
)

// SecurityService handles business logic for the unified security registry.
type SecurityService struct {
	*core.BaseComponent
	Dao       *dao.SecurityRegistryDao   `infra:"dep:dao_security_registry"`
	RedisComp *infraRedis.RedisComponent `infra:"dep:redis?"`
}

func NewSecurityService() *SecurityService {
	return &SecurityService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SECURITY, consts.COMPONENT_LOGGING),
	}
}

func (s *SecurityService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_security_registry is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *SecurityService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *SecurityService) BatchUpsert(ctx context.Context, list []*model.SecurityRegistry, chunkSize int) (int64, error) {
	logging.Infof(ctx, "SecurityService BatchUpsert %d records", len(list))
	affected, err := s.Dao.BatchUpsert(ctx, list, chunkSize)
	if err != nil {
		return affected, err
	}
	s.invalidateAggregateCaches(ctx, list)
	return affected, nil
}

func (s *SecurityService) Get(ctx context.Context, symbol, assetType, market string) (*model.SecurityRegistry, error) {
	if assetType == "" {
		assetType = bizConsts.ASSET_TYPE_STOCK
	}
	if market == "" {
		market = bizConsts.MARKET_ZH_A
	}
	return s.Dao.Get(ctx, symbol, assetType, market)
}

func (s *SecurityService) ListFiltered(ctx context.Context, f *model.SecurityFilters, limit, offset int) ([]*model.SecurityRegistry, error) {
	assetType, market, cacheable := securityAggregateCacheScope(f, limit, offset)
	if cacheable {
		key := bizConsts.BuildSecurityListCacheKey(assetType, market)
		if cached, hit, err := cache.GetJSON[[]*model.SecurityRegistry](ctx, s.redisClient(), key); err == nil && hit {
			return cached, nil
		} else if err != nil {
			logging.Warnf(ctx, "security list redis cache get failed: %v", err)
		}

		list, err := s.Dao.ListFiltered(ctx, f, limit, offset)
		if err != nil {
			return nil, err
		}
		if err := cache.SetJSON(ctx, s.redisClient(), key, time.Duration(bizConsts.RedisCacheTTLSecondsSecurityList)*time.Second, list); err != nil {
			logging.Warnf(ctx, "security list redis cache set failed: %v", err)
		}
		return list, nil
	}
	return s.Dao.ListFiltered(ctx, f, limit, offset)
}

func (s *SecurityService) CountFiltered(ctx context.Context, f *model.SecurityFilters) (int64, error) {
	assetType, market, cacheable := securityAggregateCacheScope(f, 0, 0)
	if cacheable {
		key := bizConsts.BuildSecurityCountCacheKey(assetType, market)
		if cached, hit, err := cache.GetJSON[int64](ctx, s.redisClient(), key); err == nil && hit {
			return cached, nil
		} else if err != nil {
			logging.Warnf(ctx, "security count redis cache get failed: %v", err)
		}

		count, err := s.Dao.CountFiltered(ctx, f)
		if err != nil {
			return 0, err
		}
		if err := cache.SetJSON(ctx, s.redisClient(), key, time.Duration(bizConsts.RedisCacheTTLSecondsSecurityCount)*time.Second, count); err != nil {
			logging.Warnf(ctx, "security count redis cache set failed: %v", err)
		}
		return count, nil
	}
	return s.Dao.CountFiltered(ctx, f)
}

func (s *SecurityService) DeleteAll(ctx context.Context, assetType, market string) (int64, error) {
	logging.Infof(ctx, "SecurityService DeleteAll asset_type=%s market=%s", assetType, market)
	affected, err := s.Dao.DeleteAll(ctx, assetType, market)
	if err != nil {
		return affected, err
	}
	if assetType == "" || market == "" {
		if err := s.invalidateAggregateCachesByScope(ctx, assetType, market); err != nil {
			logging.Warnf(ctx, "security cache wildcard invalidation after delete_all failed: %v", err)
		}
		return affected, nil
	}
	resolvedAssetType, resolvedMarket := normalizeSecurityAggregateScope(assetType, market)
	if delErr := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildSecurityListCacheKey(resolvedAssetType, resolvedMarket), bizConsts.BuildSecurityCountCacheKey(resolvedAssetType, resolvedMarket)); delErr != nil {
		logging.Warnf(ctx, "security cache invalidation after delete_all failed: %v", delErr)
	}
	return affected, nil
}

func (s *SecurityService) redisClient() redislib.UniversalClient {
	if s.RedisComp == nil {
		return nil
	}
	return s.RedisComp.Client()
}

func (s *SecurityService) invalidateAggregateCaches(ctx context.Context, list []*model.SecurityRegistry) {
	if len(list) == 0 {
		return
	}
	touched := make(map[string]struct{})
	keys := make([]string, 0, len(list)*2)
	for _, item := range list {
		if item == nil {
			continue
		}
		assetType, market := normalizeSecurityAggregateScope(item.AssetType, item.Market)
		scope := assetType + ":" + market
		if _, ok := touched[scope]; ok {
			continue
		}
		touched[scope] = struct{}{}
		keys = append(keys,
			bizConsts.BuildSecurityListCacheKey(assetType, market),
			bizConsts.BuildSecurityCountCacheKey(assetType, market),
		)
	}
	if err := cache.DeleteKeys(ctx, s.redisClient(), keys...); err != nil {
		logging.Warnf(ctx, "security cache invalidation after batch_upsert failed: %v", err)
	}
}

func (s *SecurityService) invalidateAggregateCachesByScope(ctx context.Context, assetType, market string) error {
	listPattern := bizConsts.BuildSecurityListCachePattern(assetType, market)
	countPattern := bizConsts.BuildSecurityCountCachePattern(assetType, market)
	if err := cache.DeleteByPattern(ctx, s.redisClient(), listPattern); err != nil {
		return err
	}
	return cache.DeleteByPattern(ctx, s.redisClient(), countPattern)
}

func securityAggregateCacheScope(f *model.SecurityFilters, limit, offset int) (string, string, bool) {
	if limit > 0 || offset > 0 {
		return "", "", false
	}
	assetType, market := normalizeSecurityAggregateScope("", "")
	if f == nil {
		return assetType, market, true
	}
	assetType, market = normalizeSecurityAggregateScope(f.AssetType, f.Market)
	if f.Symbol != "" || len(f.Symbols) > 0 || f.Exchange != "" || len(f.Exchanges) > 0 || f.Name != "" || f.Status != "" {
		return "", "", false
	}
	return assetType, market, true
}

func normalizeSecurityAggregateScope(assetType, market string) (string, string) {
	if assetType == "" {
		assetType = bizConsts.ASSET_TYPE_STOCK
	}
	if market == "" {
		market = bizConsts.MARKET_ZH_A
	}
	return assetType, market
}

// ConvertFromLegacy creates a SecurityRegistry from legacy StockZhAList fields.
func ConvertFromLegacy(symbol, name, exchange string) *model.SecurityRegistry {
	return &model.SecurityRegistry{
		Symbol:    symbol,
		AssetType: bizConsts.ASSET_TYPE_STOCK,
		Market:    bizConsts.MARKET_ZH_A,
		Exchange:  exchange,
		Name:      name,
		Status:    "active",
	}
}

// ConvertToLegacy converts a SecurityRegistry to legacy StockZhAList format.
func ConvertToLegacy(s *model.SecurityRegistry) map[string]any {
	return map[string]any{
		"code":     s.Symbol,
		"company":  s.Name,
		"exchange": s.Exchange,
	}
}

// ConvertToLegacyList converts a list of SecurityRegistry to legacy format.
func ConvertToLegacyList(list []*model.SecurityRegistry) []map[string]any {
	out := make([]map[string]any, 0, len(list))
	for _, s := range list {
		out = append(out, map[string]any{
			"code":     s.Symbol,
			"company":  s.Name,
			"exchange": s.Exchange,
		})
	}
	return out
}

// LegacyBatchUpsertFromStockList handles legacy /api/v1/stock/list/batch_upsert payload.
func (s *SecurityService) LegacyBatchUpsertFromStockList(ctx context.Context, legacyList []map[string]any) (int64, error) {
	var list []*model.SecurityRegistry
	for _, item := range legacyList {
		symbol, _ := item["code"].(string)
		name, _ := item["company"].(string)
		exchange, _ := item["exchange"].(string)
		if symbol == "" {
			continue
		}
		list = append(list, ConvertFromLegacy(symbol, name, exchange))
	}
	if len(list) == 0 {
		return 0, fmt.Errorf("no valid items in batch")
	}
	return s.BatchUpsert(ctx, list, 200)
}
