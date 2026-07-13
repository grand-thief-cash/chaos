package service

import (
	"context"
	"errors"
	"sync"
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
	Resolve   *ResolveCache              `infra:"dep:svc_resolve_cache?"`
	RedisComp *infraRedis.RedisComponent `infra:"dep:redis?"`

	// L1 process-local snapshot cache + singleflight gate (see security_search.go).
	l1Mu       sync.RWMutex
	l1         map[string]*securitySnapshot
	inflightMu sync.Mutex
	inflight   map[string]*snapshotCall
}

func NewSecurityService() *SecurityService {
	return &SecurityService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SECURITY, consts.COMPONENT_LOGGING),
		l1:            make(map[string]*securitySnapshot),
		inflight:      make(map[string]*snapshotCall),
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
	s.invalidateAllSecurityCaches(ctx)
	// New securities (or reassignment after a delete+reimport) change the natural-key → id
	// map the taxonomy resolve cache holds; invalidate so industry writes don't resolve to
	// stale/missing ids within the TTL window (refactor §8.bis-1).
	if s.Resolve != nil {
		s.Resolve.Invalidate()
	}
	return affected, nil
}

// Get retrieves a security by its natural key (exchange, asset_type, symbol).
// asset_type defaults to stock. Used for resolve (natural key -> row with id).
func (s *SecurityService) Get(ctx context.Context, exchange, assetType, symbol string) (*model.SecurityRegistry, error) {
	if assetType == "" {
		assetType = bizConsts.ASSET_TYPE_STOCK
	}
	return s.Dao.Get(ctx, exchange, assetType, symbol)
}

// GetByID retrieves a security by its surrogate id.
func (s *SecurityService) GetByID(ctx context.Context, id uint64) (*model.SecurityRegistry, error) {
	return s.Dao.GetByID(ctx, id)
}

// GetAll returns all securities, used to build resolve caches.
func (s *SecurityService) GetAll(ctx context.Context) ([]*model.SecurityRegistry, error) {
	return s.Dao.GetAll(ctx)
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
	// Refuse if downstream tables still reference securities in this scope — with no real FK
	// (§6 R9) a bare delete would leave dangling security_id refs in taxonomy_security_map /
	// industry_constituent / industry_weight (Phase 2) and financial_statement /
	// corporate_action / equity_structure / adjust_factor / long_hu_bang (Phase 3). Operator
	// must clear dependents first (this is a rebuild-only op; refactor §5.1.1/§8.bis). Mirrors
	// TaxonomyService.DeleteCategory.
	referenced, err := s.Dao.SecurityScopeHasReferences(ctx, assetType, market)
	if err != nil {
		return 0, err
	}
	if referenced {
		return 0, NewConflictError("securities in scope (asset_type=%s market=%s) are referenced by downstream tables (taxonomy_security_map/industry_constituent/industry_weight/financial_statement/corporate_action/equity_structure/adjust_factor/long_hu_bang); remove dependents first", assetType, market)
	}
	affected, err := s.Dao.DeleteAll(ctx, assetType, market)
	if err != nil {
		return affected, err
	}
	// A delete+reimport reassigns BIGSERIAL ids; the taxonomy resolve cache MUST be cleared
	// so industry writes don't resolve to now-reassigned ids (refactor §8.bis-1).
	if s.Resolve != nil {
		s.Resolve.Invalidate()
	}
	// L1 holds every scope's snapshot locally; clear it so this replica serves
	// fresh data immediately (other replicas converge via the L1 TTL).
	s.invalidateL1()
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

// invalidateAllSecurityCaches clears L1 (process-local) and pattern-deletes the
// entire security:list / security:count Redis namespace. Used on BatchUpsert:
// broad invalidation covers the case where a security's market/asset_type was
// reassigned (the old scope's cache would otherwise linger until its 6h TTL).
// Registry upserts are low-frequency batch ops, so a namespace-wide scan is
// cheap and correct. Other replicas' L1 converges via the L1 TTL (v1 SLA).
func (s *SecurityService) invalidateAllSecurityCaches(ctx context.Context) {
	s.invalidateL1()
	client := s.redisClient()
	if client == nil {
		return
	}
	if err := cache.DeleteByPattern(ctx, client, bizConsts.BuildSecurityListCachePattern("", "")); err != nil {
		logging.Warnf(ctx, "security list cache pattern invalidation failed: %v", err)
	}
	if err := cache.DeleteByPattern(ctx, client, bizConsts.BuildSecurityCountCachePattern("", "")); err != nil {
		logging.Warnf(ctx, "security count cache pattern invalidation failed: %v", err)
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
	if f.SecurityID != 0 || f.Symbol != "" || len(f.Symbols) > 0 || f.Exchange != "" || len(f.Exchanges) > 0 || f.Name != "" || f.Status != "" {
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
