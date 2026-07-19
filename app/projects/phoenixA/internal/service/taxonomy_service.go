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
	Resolve   *ResolveCache              `infra:"dep:svc_resolve_cache"`
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
	if s.Resolve == nil {
		return errors.New("svc_resolve_cache is nil (required for Phase 2 resolve + orphan defense)")
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
	s.invalidateAllMappingBySecurityCaches(ctx)
	s.Resolve.Invalidate() // new categories may introduce new index_code → category_id mappings
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

// DeleteCategory deletes a category. Refuses if any taxonomy_security_map /
// industry_constituent / industry_weight / industry_daily row still references it — with
// no real FK (§6 R9) a bare delete would leave dangling category_id references.
func (s *TaxonomyService) DeleteCategory(ctx context.Context, source, taxonomy, market, code string) error {
	cat, err := s.Dao.GetCategory(ctx, source, taxonomy, market, code)
	if err != nil {
		return err
	}
	referenced, err := s.Dao.CategoryHasReferences(ctx, cat.ID)
	if err != nil {
		return err
	}
	if referenced {
		return NewConflictError("category %s (id=%d) is referenced by taxonomy_security_map/industry_constituent/industry_weight/industry_daily; remove dependents first", code, cat.ID)
	}
	if err := s.Dao.DeleteCategory(ctx, source, taxonomy, market, code); err != nil {
		return err
	}
	s.invalidateCategoryCaches(ctx, source, taxonomy, market)
	s.invalidateAllMappingBySecurityCaches(ctx)
	s.Resolve.Invalidate()
	return nil
}

// ValidationError signals a client payload problem (unknown security_id / category_id,
// unresolvable natural key, empty sync scope, etc.). Controllers map it to 400 Bad Request,
// not 500 — it is not an internal error.
type ValidationError struct{ Msg string }

func (e *ValidationError) Error() string { return e.Msg }

// NewValidationError wraps a formatted message as a ValidationError.
func NewValidationError(format string, args ...any) *ValidationError {
	return &ValidationError{Msg: fmt.Sprintf(format, args...)}
}

// ConflictError signals a request that conflicts with current resource state (e.g. deleting
// a category / security that downstream tables still reference). Controllers map it to 409.
type ConflictError struct{ Msg string }

func (e *ConflictError) Error() string { return e.Msg }

// NewConflictError wraps a formatted message as a ConflictError.
func NewConflictError(format string, args ...any) *ConflictError {
	return &ConflictError{Msg: fmt.Sprintf(format, args...)}
}

// validateMappingIDs checks that every security_id and category_id in a direct mapping
// write exists, rejecting orphan-id writes (no real FK, §6 R9 → app-layer defense, §10.c).
// A cache/DB load failure is returned as a plain error (→ 500); a genuine miss is a
// ValidationError (→ 400).
func (s *TaxonomyService) validateMappingIDs(ctx context.Context, securityIDs, categoryIDs []uint64) error {
	for _, id := range securityIDs {
		found, err := s.Resolve.SecurityExists(ctx, id)
		if err != nil {
			return fmt.Errorf("check security_id %d: %w", id, err)
		}
		if !found {
			return NewValidationError("security_id %d does not exist in security_registry", id)
		}
	}
	for _, id := range categoryIDs {
		found, err := s.Resolve.CategoryExists(ctx, id)
		if err != nil {
			return fmt.Errorf("check category_id %d: %w", id, err)
		}
		if !found {
			return NewValidationError("category_id %d does not exist in taxonomy_category", id)
		}
	}
	return nil
}

// BatchUpsertMappings upserts taxonomy-security mappings (id-keyed). Validates that every
// security_id / category_id exists before writing (orphan defense).
func (s *TaxonomyService) BatchUpsertMappings(ctx context.Context, list []*model.TaxonomySecurityMap) error {
	secIDs := make([]uint64, 0, len(list))
	catIDs := make([]uint64, 0, len(list))
	for _, m := range list {
		if m == nil {
			continue
		}
		secIDs = append(secIDs, m.SecurityID)
		catIDs = append(catIDs, m.CategoryID)
	}
	if err := s.validateMappingIDs(ctx, secIDs, catIDs); err != nil {
		return err
	}
	if err := s.Dao.BatchUpsertMappings(ctx, list); err != nil {
		return err
	}
	s.invalidateMappingCachesForList(ctx, list)
	return nil
}

// ReplaceSecuritiesForCategories replaces all securities for given categories.
// payload: category_id → []security_id. Validates all ids exist first.
func (s *TaxonomyService) ReplaceSecuritiesForCategories(ctx context.Context, payload map[uint64][]uint64) error {
	secIDs := make([]uint64, 0)
	catIDs := make([]uint64, 0, len(payload))
	for cat, secs := range payload {
		catIDs = append(catIDs, cat)
		secIDs = append(secIDs, secs...)
	}
	if err := s.validateMappingIDs(ctx, secIDs, catIDs); err != nil {
		return err
	}
	if err := s.Dao.ReplaceSecuritiesForCategories(ctx, payload); err != nil {
		return err
	}
	s.invalidateMappingCachesForCategoryPayload(ctx, payload)
	return nil
}

// ReplaceCategoriesForSecurities replaces all categories for given securities.
// payload: security_id → []category_id. Validates all ids exist first.
func (s *TaxonomyService) ReplaceCategoriesForSecurities(ctx context.Context, payload map[uint64][]uint64) error {
	secIDs := make([]uint64, 0, len(payload))
	catIDs := make([]uint64, 0)
	for sec, cats := range payload {
		secIDs = append(secIDs, sec)
		catIDs = append(catIDs, cats...)
	}
	if err := s.validateMappingIDs(ctx, secIDs, catIDs); err != nil {
		return err
	}
	if err := s.Dao.ReplaceCategoriesForSecurities(ctx, payload); err != nil {
		return err
	}
	s.invalidateMappingCachesForSecurityPayload(ctx, payload)
	return nil
}

// ListMappingsByCategory returns mappings for a category_id.
func (s *TaxonomyService) ListMappingsByCategory(ctx context.Context, categoryID uint64, page, pageSize int) ([]*model.TaxonomySecurityMap, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	cacheKey := bizConsts.BuildTaxonomyMappingByCategoryCacheKey(categoryID)
	if cached, hit, err := cache.GetJSON[[]*model.TaxonomySecurityMap](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return paginateItems(cached, page, pageSize), nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListMappingsByCategory(ctx, categoryID, 0, 0)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyMappingByCategory)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category redis cache set failed: %v", err)
	}
	return paginateItems(list, page, pageSize), nil
}

// ListMappingsBySecurity returns all taxonomy mappings for a given security_id, enriched
// with category hierarchy + canonical fields. Security display fields (symbol / asset_type /
// market) are filled from the resolve cache.
func (s *TaxonomyService) ListMappingsBySecurity(ctx context.Context, securityID uint64) ([]*model.TaxonomySecurityMapWithDetail, error) {
	cacheKey := bizConsts.BuildTaxonomyMappingBySecurityCacheKey(securityID)
	if cached, hit, err := cache.GetJSON[[]*model.TaxonomySecurityMapWithDetail](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return cached, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-security redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListMappingsBySecurityID(ctx, securityID)
	if err != nil {
		return nil, err
	}
	// Enrich security display fields (symbol/asset_type/market) from the resolve cache.
	// A cache failure here only degrades display fields (the id-keyed data is already
	// correct from the DAO), so log + skip rather than failing the read. But do NOT cache
	// a degraded result — otherwise a transient resolve-cache failure would pin a
	// display-field-less response for the full TTL (14d) even after recovery.
	enrichmentFailed := false
	for _, d := range list {
		if d == nil {
			continue
		}
		sec, ok, err := s.Resolve.ResolveSecurity(ctx, d.SecurityID)
		if err != nil {
			enrichmentFailed = true
			logging.Warnf(ctx, "ListMappingsBySecurity: resolve security_id=%d for display failed: %v", d.SecurityID, err)
			continue
		}
		if ok {
			d.Symbol = sec.Symbol
			d.AssetType = sec.AssetType
			if d.Market == "" {
				d.Market = sec.Market
			}
		}
	}
	if !enrichmentFailed {
		if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyMappingBySecurity)*time.Second, list); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-security redis cache set failed: %v", err)
		}
	} else {
		logging.Warnf(ctx, "ListMappingsBySecurity: skipping redis cache write (enrichment failed; degraded response returned uncached)")
	}
	return list, nil
}

// DeleteMapping deletes a single mapping by (category_id, security_id).
func (s *TaxonomyService) DeleteMapping(ctx context.Context, categoryID, securityID uint64) error {
	if err := s.Dao.DeleteMapping(ctx, categoryID, securityID); err != nil {
		return err
	}
	s.invalidateMappingCaches(ctx, categoryID, securityID)
	return nil
}

// SyncMappingsFromConstituents derives category→security mappings from industry_constituent
// (single-table SELECT DISTINCT, no JOIN — refactor §2.3). The path's (source, taxonomy,
// market) is resolved to a set of category_ids which scope the SELECT.
func (s *TaxonomyService) SyncMappingsFromConstituents(ctx context.Context, source, taxonomy, market string) (int64, error) {
	if source == "" || taxonomy == "" {
		return 0, errors.New("source and taxonomy are required")
	}
	categoryIDs, err := s.Resolve.CategoryIDsForScope(ctx, source, taxonomy, market)
	if err != nil {
		// Cache/dependency failure — do NOT swallow as 0 rows (refactor §10.c).
		return 0, fmt.Errorf("resolve scope for sync: %w", err)
	}
	if len(categoryIDs) == 0 {
		// Empty scope = either a misspelled (source, taxonomy, market) or taxonomy_category
		// not yet imported for this scope. Treat as a prerequisite failure rather than a
		// silent 0-row success so the caller can detect the mistake (refactor §2.3/§9.bis).
		return 0, NewValidationError("no taxonomy_category rows found for scope (source=%s taxonomy=%s market=%s); verify the path or import categories first", source, taxonomy, market)
	}
	n, err := s.Dao.SyncMappingsFromConstituents(ctx, categoryIDs)
	if err != nil {
		return 0, err
	}
	s.invalidateMappingCachesForScope(ctx)
	logging.Infof(ctx, "TaxonomyService SyncMappingsFromConstituents source=%s taxonomy=%s market=%s categories=%d rows=%d", source, taxonomy, market, len(categoryIDs), n)
	return n, nil
}

// ──────────── Industry Constituents ────────────

// ResolveConstituents resolves each constituent's IndexCode → CategoryID and ConCode →
// SecurityID against the in-memory cache, populating the id fields in place. The caller
// (controller) invokes this BEFORE routing to the write buffer or the direct DAO path so
// that buffered payloads are already resolved physical rows (refactor §10.d.3). A single
// unresolved row rejects the whole batch (refactor §10.c — no silent orphan ids).
func (s *TaxonomyService) ResolveConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	for i, c := range list {
		if c == nil {
			continue
		}
		catID, found, err := s.Resolve.ResolveCategoryID(ctx, source, taxonomy, market, c.IndexCode)
		if err != nil {
			return fmt.Errorf("constituent row %d: resolve category for index_code=%q: %w", i, c.IndexCode, err)
		}
		if !found {
			return NewValidationError("constituent row %d: category not found for index_code=%q (source=%s taxonomy=%s market=%s); ensure taxonomy_category has been imported", i, c.IndexCode, source, taxonomy, market)
		}
		secID, err := s.Resolve.resolveConstituentSecurity(ctx, c.ConCode, c.Symbol)
		if err != nil {
			// Preserve error type: ValidationError (format/not-found) → 400, plain (load) → 500.
			return fmt.Errorf("constituent row %d (index_code=%s): %w", i, c.IndexCode, err)
		}
		c.CategoryID = catID
		c.SecurityID = secID
	}
	return nil
}

// BatchUpsertConstituents upserts industry index constituents (must be pre-resolved).
func (s *TaxonomyService) BatchUpsertConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertConstituents source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	if err := s.Dao.BatchUpsertConstituents(ctx, source, taxonomy, market, list); err != nil {
		return err
	}
	s.invalidateConstituentCachesForConstituents(ctx, list)
	return nil
}

// ListConstituentsByCategory returns all constituents for a category_id.
func (s *TaxonomyService) ListConstituentsByCategory(ctx context.Context, categoryID uint64, page, pageSize int) ([]*model.IndustryConstituent, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	cacheKey := bizConsts.BuildTaxonomyConstituentsByCategoryCacheKey(categoryID)
	if cached, hit, err := cache.GetJSON[[]*model.IndustryConstituent](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return paginateItems(cached, page, pageSize), nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-category redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListConstituentsByCategory(ctx, categoryID, 0, 0)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyConstituentsByCategory)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-category redis cache set failed: %v", err)
	}
	return paginateItems(list, page, pageSize), nil
}

// ListConstituentsBySecurity returns all index memberships for a constituent security_id.
func (s *TaxonomyService) ListConstituentsBySecurity(ctx context.Context, securityID uint64) ([]*model.IndustryConstituent, error) {
	cacheKey := bizConsts.BuildTaxonomyConstituentsBySecurityCacheKey(securityID)
	if cached, hit, err := cache.GetJSON[[]*model.IndustryConstituent](ctx, s.redisClient(), cacheKey); err == nil && hit {
		return cached, nil
	} else if err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-security redis cache get failed: %v", err)
	}
	list, err := s.Dao.ListConstituentsBySecurity(ctx, securityID)
	if err != nil {
		return nil, err
	}
	if err := cache.SetJSON(ctx, s.redisClient(), cacheKey, time.Duration(bizConsts.RedisCacheTTLSecondsTaxonomyConstituentsBySecurity)*time.Second, list); err != nil {
		logging.Warnf(ctx, "taxonomy constituents-by-security redis cache set failed: %v", err)
	}
	return list, nil
}

// ──────────── Industry Weights ────────────

// ResolveWeights resolves each weight's IndexCode → CategoryID and ConCode → SecurityID.
// Must be called before routing to the write buffer (refactor §10.d.3).
func (s *TaxonomyService) ResolveWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	for i, w := range list {
		if w == nil {
			continue
		}
		catID, found, err := s.Resolve.ResolveCategoryID(ctx, source, taxonomy, market, w.IndexCode)
		if err != nil {
			return fmt.Errorf("weight row %d: resolve category for index_code=%q: %w", i, w.IndexCode, err)
		}
		if !found {
			return NewValidationError("weight row %d: category not found for index_code=%q", i, w.IndexCode)
		}
		secID, err := s.Resolve.resolveConstituentSecurity(ctx, w.ConCode, w.Symbol)
		if err != nil {
			return fmt.Errorf("weight row %d (index_code=%s): %w", i, w.IndexCode, err)
		}
		w.CategoryID = catID
		w.SecurityID = secID
	}
	return nil
}

// BatchUpsertWeights upserts industry index constituent daily weights (must be pre-resolved).
func (s *TaxonomyService) BatchUpsertWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertWeights source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertWeights(ctx, source, taxonomy, market, list)
}

// ListWeightsByCategoryAndDate returns weights for a given category_id on a given trade_date.
func (s *TaxonomyService) ListWeightsByCategoryAndDate(ctx context.Context, categoryID uint64, tradeDate string) ([]*model.IndustryWeight, error) {
	return s.Dao.ListWeightsByCategoryAndDate(ctx, categoryID, tradeDate)
}

// ──────────── Industry Daily ────────────

// ResolveIndustryDaily resolves each row's IndexCode → CategoryID. Index-level data has no
// security_id. Must be called before routing to the write buffer (refactor §10.d.3).
func (s *TaxonomyService) ResolveIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	for i, r := range list {
		if r == nil {
			continue
		}
		catID, found, err := s.Resolve.ResolveCategoryID(ctx, source, taxonomy, market, r.IndexCode)
		if err != nil {
			return fmt.Errorf("industry-daily row %d: resolve category for index_code=%q: %w", i, r.IndexCode, err)
		}
		if !found {
			return NewValidationError("industry-daily row %d: category not found for index_code=%q", i, r.IndexCode)
		}
		r.CategoryID = catID
	}
	return nil
}

// BatchUpsertIndustryDaily upserts industry index daily bars (must be pre-resolved).
func (s *TaxonomyService) BatchUpsertIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertIndustryDaily source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertIndustryDaily(ctx, source, taxonomy, market, list)
}

// QueryIndustryDaily queries industry daily bars by category_id.
func (s *TaxonomyService) QueryIndustryDaily(ctx context.Context, categoryID uint64, startDate, endDate string, limit int) ([]*model.IndustryDaily, error) {
	if limit < 1 {
		limit = 5000
	}
	return s.Dao.QueryIndustryDaily(ctx, categoryID, startDate, endDate, limit)
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

func (s *TaxonomyService) invalidateMappingCaches(ctx context.Context, categoryID, securityID uint64) {
	client := s.redisClient()
	if securityID != 0 {
		if err := cache.DeleteKeys(ctx, client, bizConsts.BuildTaxonomyMappingBySecurityCacheKey(securityID)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-security cache invalidation failed: %v", err)
		}
	}
	if categoryID != 0 {
		if err := cache.DeleteKeys(ctx, client, bizConsts.BuildTaxonomyMappingByCategoryCacheKey(categoryID)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-category cache invalidation failed: %v", err)
		}
	}
}

func (s *TaxonomyService) invalidateMappingCachesForScope(ctx context.Context) {
	client := s.redisClient()
	if err := cache.DeleteByPattern(ctx, client, bizConsts.BuildTaxonomyMappingByCategoryCachePattern()); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-category scope invalidation failed: %v", err)
	}
	s.invalidateAllMappingBySecurityCaches(ctx)
}

func (s *TaxonomyService) invalidateAllMappingBySecurityCaches(ctx context.Context) {
	if err := cache.DeleteByPattern(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySecurityCachePattern()); err != nil {
		logging.Warnf(ctx, "taxonomy mapping-by-security wildcard invalidation failed: %v", err)
	}
}

func (s *TaxonomyService) invalidateMappingCachesForList(ctx context.Context, list []*model.TaxonomySecurityMap) {
	for _, item := range list {
		if item == nil {
			continue
		}
		s.invalidateMappingCaches(ctx, item.CategoryID, item.SecurityID)
	}
}

func (s *TaxonomyService) invalidateMappingCachesForCategoryPayload(ctx context.Context, payload map[uint64][]uint64) {
	for categoryID, securityIDs := range payload {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingByCategoryCacheKey(categoryID)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-category payload invalidation failed: %v", err)
		}
		for _, securityID := range securityIDs {
			if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySecurityCacheKey(securityID)); err != nil {
				logging.Warnf(ctx, "taxonomy mapping-by-security payload invalidation failed: %v", err)
			}
		}
	}
}

func (s *TaxonomyService) invalidateMappingCachesForSecurityPayload(ctx context.Context, payload map[uint64][]uint64) {
	for securityID, categoryIDs := range payload {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingBySecurityCacheKey(securityID)); err != nil {
			logging.Warnf(ctx, "taxonomy mapping-by-security payload invalidation failed: %v", err)
		}
		for _, categoryID := range categoryIDs {
			if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyMappingByCategoryCacheKey(categoryID)); err != nil {
				logging.Warnf(ctx, "taxonomy mapping-by-category payload invalidation failed: %v", err)
			}
		}
	}
}

func (s *TaxonomyService) invalidateConstituentCachesForConstituents(ctx context.Context, list []*model.IndustryConstituent) {
	seenCategories := make(map[uint64]struct{})
	seenSecurities := make(map[uint64]struct{})
	for _, item := range list {
		if item == nil {
			continue
		}
		if item.CategoryID != 0 {
			seenCategories[item.CategoryID] = struct{}{}
		}
		if item.SecurityID != 0 {
			seenSecurities[item.SecurityID] = struct{}{}
		}
	}
	for categoryID := range seenCategories {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyConstituentsByCategoryCacheKey(categoryID)); err != nil {
			logging.Warnf(ctx, "taxonomy constituents-by-category invalidation failed: %v", err)
		}
	}
	for securityID := range seenSecurities {
		if err := cache.DeleteKeys(ctx, s.redisClient(), bizConsts.BuildTaxonomyConstituentsBySecurityCacheKey(securityID)); err != nil {
			logging.Warnf(ctx, "taxonomy constituents-by-security invalidation failed: %v", err)
		}
	}
}
