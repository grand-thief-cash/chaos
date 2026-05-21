package service

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
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

// TaxonomyService is the unified service for taxonomy categories and mappings.
type TaxonomyService struct {
	*core.BaseComponent
	Dao       *dao.TaxonomyDao           `infra:"dep:dao_taxonomy"`
	RedisComp *infraRedis.RedisComponent `infra:"dep:redis?"`
}

func NewTaxonomyService() *TaxonomyService {
	return &TaxonomyService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_TAXONOMY, consts.COMPONENT_LOGGING),
	}
}

func (s *TaxonomyService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_taxonomy is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *TaxonomyService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *TaxonomyService) redisClient() redislib.UniversalClient {
	if s.RedisComp == nil {
		return nil
	}
	return s.RedisComp.Client()
}

// BatchUpsertCategories upserts taxonomy categories.
func (s *TaxonomyService) BatchUpsertCategories(ctx context.Context, source, taxonomy, market string, list []*model.TaxonomyCategory) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertCategories source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	if err := s.Dao.BatchUpsertCategories(ctx, source, taxonomy, market, list); err != nil {
		return err
	}
	s.invalidateCategoryCaches(ctx, source, taxonomy, market)
	s.invalidateAllMappingBySymbolCaches(ctx)
	return nil
}

// ListCategories lists taxonomy categories.
func (s *TaxonomyService) ListCategories(ctx context.Context, source, taxonomy, market string, f *model.TaxonomyCategoryFilters, page, pageSize int) ([]*model.TaxonomyCategory, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	cacheKey := bizConsts.BuildTaxonomyCategoryListCacheKey(source, taxonomy, market, taxonomyCategoryFilterToken(f))
	if cached, hit, err := cache.GetJSON[taxonomyCategoryListCachePayload](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return paginateItems(cached.List, page, pageSize), cached.Total, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy categories redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListCategories(ctx, source, taxonomy, market, f, 0, 0)
	if err != nil {
		return nil, 0, err
	}
	count := int64(len(list))
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyCategoryList)*time.Second, taxonomyCategoryListCachePayload{List: list, Total: count}); err != nil {
		logging.Warnf(ctx, "taxonomy categories redis cache set failed: %v", err)
	}
	return paginateItems(list, page, pageSize), count, nil
}

// GetCategory retrieves a single category.
func (s *TaxonomyService) GetCategory(ctx context.Context, source, taxonomy, market, code string) (*model.TaxonomyCategory, error) {
	cacheKey := bizConsts.BuildTaxonomyCategoryGetCacheKey(source, taxonomy, market, code)
	if cached, hit, err := cache.GetJSON[model.TaxonomyCategory](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return &cached, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy category redis cache get failed: %v", err)
	}
	cat, err := s.Dao.GetCategory(ctx, source, taxonomy, market, code)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyCategoryGet)*time.Second, cat); err != nil {
		logging.Warnf(ctx, "taxonomy category redis cache set failed: %v", err)
	}
	return cat, nil
}

// DeleteCategory deletes a category.
func (s *TaxonomyService) DeleteCategory(ctx context.Context, source, taxonomy, market, code string) error {
	if err := s.Dao.DeleteCategory(ctx, source, taxonomy, market, code); err != nil {
		return err
	}
	s.invalidateCategoryCaches(ctx, source, taxonomy, market)
	s.invalidateAllMappingBySymbolCaches(ctx)
	return nil
}

// BatchUpsertMappings upserts taxonomy-security mappings.
func (s *TaxonomyService) BatchUpsertMappings(ctx context.Context, source, taxonomy string, list []*model.TaxonomySecurityMap) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	if err := s.Dao.BatchUpsertMappings(ctx, source, taxonomy, list); err != nil {
		return err
	}
	s.invalidateMappingCachesForList(ctx, source, taxonomy, list)
	return nil
}

// ReplaceStocksForCategories replaces all symbols for given categories.
func (s *TaxonomyService) ReplaceStocksForCategories(ctx context.Context, source, taxonomy string, payload map[string][]string) error {
	if err := s.Dao.ReplaceStocksForCategories(ctx, source, taxonomy, payload); err != nil {
		return err
	}
	s.invalidateMappingCachesForCategoryPayload(ctx, source, taxonomy, payload)
	return nil
}

// ReplaceCategoriesForSymbols replaces all categories for given symbols.
func (s *TaxonomyService) ReplaceCategoriesForSymbols(ctx context.Context, source, taxonomy string, payload map[string][]string) error {
	if err := s.Dao.ReplaceCategoriesForSymbols(ctx, source, taxonomy, payload); err != nil {
		return err
	}
	s.invalidateMappingCachesForSymbolPayload(ctx, source, taxonomy, payload)
	return nil
}

// ListMappingsByCategory returns mappings for a source + taxonomy + category.
func (s *TaxonomyService) ListMappingsByCategory(ctx context.Context, source, taxonomy, categoryCode string, page, pageSize int) ([]*model.TaxonomySecurityMap, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	cacheKey := bizConsts.BuildTaxonomyMappingByCategoryCacheKey(source, taxonomy, categoryCode)
	if cached, hit, err := cache.GetJSON[[]*model.TaxonomySecurityMap](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return paginateItems(cached, page, pageSize), nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListMappingsByCategory(ctx, source, taxonomy, categoryCode, 0, 0)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyMappingByCategory)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category redis cache set failed: %v", err)
	}
	return paginateItems(list, page, pageSize), nil
}

// ListMappingsBySymbol returns all taxonomy mappings for a given symbol.
func (s *TaxonomyService) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMapWithDetail, error) {
	cacheKey := bizConsts.BuildTaxonomyMappingBySymbolCacheKey(symbol)
	if cached, hit, err := cache.GetJSON[[]*model.TaxonomySecurityMapWithDetail](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return cached, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-symbol redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListMappingsBySymbol(ctx, symbol)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyMappingBySymbol)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-symbol redis cache set failed: %v", err)
	}
	return list, nil
}

// DeleteMapping deletes a single mapping.
func (s *TaxonomyService) DeleteMapping(ctx context.Context, source, taxonomy, categoryCode, symbol string) error {
	if err := s.Dao.DeleteMapping(ctx, source, taxonomy, categoryCode, symbol); err != nil {
		return err
	}
	s.invalidateMappingCaches(ctx, source, taxonomy, categoryCode, symbol)
	return nil
}

// SyncMappingsFromConstituents derives category→symbol mappings from constituents and categories.
func (s *TaxonomyService) SyncMappingsFromConstituents(ctx context.Context, source, taxonomy, market string) (int64, error) {
	if source == "" || taxonomy == "" {
		return 0, errors.New("source and taxonomy are required")
	}
	n, err := s.Dao.SyncMappingsFromConstituents(ctx, source, taxonomy, market)
	if err != nil {
		return 0, err
	}
	s.invalidateMappingCachesForScope(ctx, source, taxonomy)
	logging.Infof(ctx, "TaxonomyService SyncMappingsFromConstituents source=%s taxonomy=%s market=%s rows=%d", source, taxonomy, market, n)
	return n, nil
}

// ──────────── Industry Constituents ────────────

// BatchUpsertConstituents upserts industry index constituents.
func (s *TaxonomyService) BatchUpsertConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertConstituents source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	if err := s.Dao.BatchUpsertConstituents(ctx, source, taxonomy, market, list); err != nil {
		return err
	}
	s.invalidateConstituentCachesForConstituents(ctx, source, taxonomy, market, list)
	return nil
}

// ListConstituentsByIndex returns all constituents for an index.
func (s *TaxonomyService) ListConstituentsByIndex(ctx context.Context, source, taxonomy, market, indexCode string, page, pageSize int) ([]*model.IndustryConstituent, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	cacheKey := bizConsts.BuildTaxonomyConstituentsByIndexCacheKey(source, taxonomy, market, indexCode)
	if cached, hit, err := cache.GetJSON[[]*model.IndustryConstituent](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return paginateItems(cached, page, pageSize), nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-index redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListConstituentsByIndex(ctx, source, taxonomy, market, indexCode, 0, 0)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyConstituentsByIndex)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-index redis cache set failed: %v", err)
	}
	return paginateItems(list, page, pageSize), nil
}

// ListConstituentsBySymbol returns all index memberships for a constituent stock.
func (s *TaxonomyService) ListConstituentsBySymbol(ctx context.Context, source, taxonomy, market, symbol string) ([]*model.IndustryConstituent, error) {
	cacheKey := bizConsts.BuildTaxonomyConstituentsBySymbolCacheKey(source, taxonomy, market, symbol)
	if cached, hit, err := cache.GetJSON[[]*model.IndustryConstituent](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return cached, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-symbol redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListConstituentsBySymbol(ctx, source, taxonomy, market, symbol)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyConstituentsBySymbol)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-symbol redis cache set failed: %v", err)
	}
	return list, nil
}

// ──────────── Industry Weights ────────────

// BatchUpsertWeights upserts industry index constituent daily weights.
func (s *TaxonomyService) BatchUpsertWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertWeights source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertWeights(ctx, source, taxonomy, market, list)
}

// ListWeightsByIndexAndDate returns weights for a given index on a given trade_date.
func (s *TaxonomyService) ListWeightsByIndexAndDate(ctx context.Context, source, taxonomy, market, indexCode, tradeDate string) ([]*model.IndustryWeight, error) {
	return s.Dao.ListWeightsByIndexAndDate(ctx, source, taxonomy, market, indexCode, tradeDate)
}

// ──────────── Industry Daily ────────────

// BatchUpsertIndustryDaily upserts industry index daily bars.
func (s *TaxonomyService) BatchUpsertIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertIndustryDaily source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertIndustryDaily(ctx, source, taxonomy, market, list)
}

// QueryIndustryDaily queries industry daily bars.
func (s *TaxonomyService) QueryIndustryDaily(ctx context.Context, source, taxonomy, market, indexCode, startDate, endDate string, limit int) ([]*model.IndustryDaily, error) {
	if limit < 1 {
		limit = 5000
	}
	return s.Dao.QueryIndustryDaily(ctx, source, taxonomy, market, indexCode, startDate, endDate, limit)
}

type taxonomyCategoryListCachePayload struct {
	List  []*model.TaxonomyCategory `json:"list"`
	Total int64                     `json:"total"`
}

func taxonomyCategoryFilterToken(f *model.TaxonomyCategoryFilters) string {
	parts := []string{}
	if f == nil {
		return "all"
	}
	if f.ParentCode != nil {
		parts = append(parts, "parent_code="+*f.ParentCode)
	}
	if f.Level != nil {
		parts = append(parts, fmt.Sprintf("level=%d", *f.Level))
	}
	if f.IsLeaf != nil {
		parts = append(parts, fmt.Sprintf("is_leaf=%t", *f.IsLeaf))
	}
	if f.Name != "" {
		parts = append(parts, "name="+f.Name)
	}
	if f.AttrsHasKey != "" {
		parts = append(parts, "attrs_has_key="+f.AttrsHasKey)
	}
	if len(f.AttrsContains) > 0 {
		keys := make([]string, 0, len(f.AttrsContains))
		for key := range f.AttrsContains {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			parts = append(parts, fmt.Sprintf("attrs_contains.%s=%v", key, f.AttrsContains[key]))
		}
	}
	if len(parts) == 0 {
		return "all"
	}
	return strings.Join(parts, "&")
}

func paginateItems[T any](items []T, page, pageSize int) []T {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		return items
	}
	start := (page - 1) * pageSize
	if start >= len(items) {
		return []T{}
	}
	end := start + pageSize
	if end > len(items) {
		end = len(items)
	}
	return items[start:end]
}

func (s *TaxonomyService) invalidateCategoryCaches(ctx context.Context, source, taxonomy, market string) {
	client := s.redisClient()
	patterns := []string{
		bizConsts.BuildTaxonomyCategoryListCachePattern(source, taxonomy, market),
		bizConsts.BuildTaxonomyCategoryGetCachePattern(source, taxonomy, market),
	}
	for _, pattern := range patterns {
		if err := cache.DeleteByPattern(ctx, client, pattern); err != nil {
			logging.Warnf(ctx, "taxonomy category cache invalidation failed: %v", err)
		}
	}
}

func (s *TaxonomyService) invalidateMappingCaches(ctx context.Context, source, taxonomy, categoryCode, symbol string) {
	client := s.redisClient()
	if symbol != "" {
		if err := cache.DeleteKeys(ctx, client, bizConsts.BuildTaxonomyMappingBySymbolCacheKey(symbol)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-symbol cache invalidation failed: %v", err)
		}
	}
	if categoryCode != "" {
		if err := cache.DeleteByPattern(ctx, client, bizConsts.BuildTaxonomyMappingByCategoryCachePattern(source, taxonomy, categoryCode)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-category cache invalidation failed: %v", err)
		}
	}
}

func (s *TaxonomyService) invalidateMappingCachesForScope(ctx context.Context, source, taxonomy string) {
	client := s.redisClient()
	if err := cache.DeleteByPattern(ctx, client, bizConsts.BuildTaxonomyMappingByCategoryCachePattern(source, taxonomy, "")); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category scope invalidation failed: %v", err)
	}
	s.invalidateAllMappingBySymbolCaches(ctx)
}

func (s *TaxonomyService) invalidateAllMappingBySymbolCaches(ctx context.Context) {
	if err := cache.DeleteByPattern(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySymbolCachePattern()); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-symbol wildcard invalidation failed: %v", err)
	}
}

func (s *TaxonomyService) invalidateMappingCachesForList(ctx context.Context, source, taxonomy string, list []*model.TaxonomySecurityMap) {
	for _, item := range list {
		if item == nil {
			continue
		}
		s.invalidateMappingCaches(ctx, source, taxonomy, item.CategoryCode, item.Symbol)
	}
}

func (s *TaxonomyService) invalidateMappingCachesForCategoryPayload(ctx context.Context, source, taxonomy string, payload map[string][]string) {
	for categoryCode, symbols := range payload {
		if err := cache.DeleteByPattern(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingByCategoryCachePattern(source, taxonomy, categoryCode)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-category payload invalidation failed: %v", err)
		}
		for _, symbol := range symbols {
			if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySymbolCacheKey(symbol)); err != nil {
				logging.Warnf(ctx, "taxonomy mapping-by-symbol payload invalidation failed: %v", err)
			}
		}
	}
}

func (s *TaxonomyService) invalidateMappingCachesForSymbolPayload(ctx context.Context, source, taxonomy string, payload map[string][]string) {
	for symbol, categories := range payload {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySymbolCacheKey(symbol)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-symbol payload invalidation failed: %v", err)
		}
		for _, categoryCode := range categories {
			if err := cache.DeleteByPattern(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingByCategoryCachePattern(source, taxonomy, categoryCode)); err != nil {
				logging.Warnf(ctx, "taxonomy mapping-by-category payload invalidation failed: %v", err)
			}
		}
	}
}

func (s *TaxonomyService) invalidateConstituentCachesForConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) {
	seenSymbols := make(map[string]struct{})
	seenIndexes := make(map[string]struct{})
	for _, item := range list {
		if item == nil {
			continue
		}
		if item.IndexCode != "" {
			seenIndexes[item.IndexCode] = struct{}{}
		}
		if item.Symbol != "" {
			seenSymbols[item.Symbol] = struct{}{}
		}
	}
	for indexCode := range seenIndexes {
		if err := cache.DeleteByPattern(ctx, s.redisClient(), bizConsts.BuildTaxonomyConstituentsByIndexCachePattern(source, taxonomy, market, indexCode)); err != nil {
			logging.Warnf(ctx, "taxonomy constituents-by-index invalidation failed: %v", err)
		}
	}
	for symbol := range seenSymbols {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyConstituentsBySymbolCacheKey(source, taxonomy, market, symbol)); err != nil {
			logging.Warnf(ctx, "taxonomy constituents-by-symbol invalidation failed: %v", err)
		}
	}
}
