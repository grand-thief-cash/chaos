package service

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// ResolveCache is the shared, process-local natural-key → surrogate-id resolver
// (refactor §2.3 / §6 R7 / §10.c). It bulk-loads security_registry + taxonomy_category
// into in-memory maps so industry_constituent / industry_weight / industry_daily upserts
// can resolve SDK natural keys (INDEX_CODE, CON_CODE) to category_id / security_id without
// a per-row DB round-trip or a derivation JOIN, and so direct mapping writes can validate
// that caller-supplied ids actually exist (no real FK, §6 R9 → app-layer orphan defense).
//
// It is a registered component shared by TaxonomyService (resolves + validates) and
// SecurityService (invalidates on security_registry upsert / delete — without this, a
// rebuild that reassigns BIGSERIAL ids would leave the cache pointing at stale ids and
// industry writes would produce orphans within the TTL window; refactor §8.bis-1).
//
// Process-local (no Redis L2 yet). Lazy-loads on first access and refreshes on a TTL so a
// long-running phoenixA picks up newly upserted rows. Within a single rebuild cycle
// surrogate ids are stable (§8.bis-1), so staleness across a rebuild boundary is not a
// concern — a rebuild clears the whole DB anyway (and SecurityService.DeleteAll now
// invalidates this cache).
type ResolveCache struct {
	*core.BaseComponent
	SecurityDao *dao.SecurityRegistryDao `infra:"dep:dao_security_registry"`
	TaxonomyDao *dao.TaxonomyDao         `infra:"dep:dao_taxonomy"`

	mu       sync.RWMutex
	loadedAt time.Time

	secByNatural map[secNaturalKey]uint64
	secByID      map[uint64]*model.SecurityRegistry
	catByNatural map[catNaturalKey]uint64
	catByID      map[uint64]*model.TaxonomyCategory
}

type secNaturalKey struct {
	exchange  string
	assetType string
	symbol    string
}

type catNaturalKey struct {
	source    string
	taxonomy  string
	market    string
	indexCode string
}

const resolveCacheTTL = 5 * time.Minute

func NewResolveCache() *ResolveCache {
	return &ResolveCache{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_RESOLVE_CACHE, consts.COMPONENT_LOGGING),
		secByNatural:  make(map[secNaturalKey]uint64),
		secByID:       make(map[uint64]*model.SecurityRegistry),
		catByNatural:  make(map[catNaturalKey]uint64),
		catByID:       make(map[uint64]*model.TaxonomyCategory),
	}
}

func (c *ResolveCache) Start(ctx context.Context) error {
	if c.SecurityDao == nil {
		return errors.New("dao_security_registry is nil")
	}
	if c.TaxonomyDao == nil {
		return errors.New("dao_taxonomy is nil")
	}
	return c.BaseComponent.Start(ctx)
}

func (c *ResolveCache) Stop(ctx context.Context) error { return c.BaseComponent.Stop(ctx) }

// normalizeCatKey trims all category natural-key parts so a stored row and a lookup that
// disagree on surrounding whitespace still match (artemis category vs constituent tasks
// are not consistent about stripping INDEX_CODE).
func normalizeCatKey(source, taxonomy, market, indexCode string) catNaturalKey {
	return catNaturalKey{
		source:    strings.TrimSpace(source),
		taxonomy:  strings.TrimSpace(taxonomy),
		market:    strings.TrimSpace(market),
		indexCode: strings.TrimSpace(indexCode),
	}
}

func (c *ResolveCache) ensureLoaded(ctx context.Context) error {
	c.mu.RLock()
	fresh := !c.loadedAt.IsZero() && time.Since(c.loadedAt) < resolveCacheTTL
	c.mu.RUnlock()
	if fresh {
		return nil
	}
	return c.reload(ctx)
}

func (c *ResolveCache) reload(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	// Double-check after acquiring the write lock.
	if !c.loadedAt.IsZero() && time.Since(c.loadedAt) < resolveCacheTTL {
		return nil
	}
	if c.SecurityDao == nil {
		return fmt.Errorf("security dao is nil")
	}
	if c.TaxonomyDao == nil {
		return fmt.Errorf("taxonomy dao is nil")
	}

	secs, err := c.SecurityDao.GetAll(ctx)
	if err != nil {
		return fmt.Errorf("load securities: %w", err)
	}
	cats, err := c.TaxonomyDao.ListAllCategories(ctx)
	if err != nil {
		return fmt.Errorf("load categories: %w", err)
	}

	secByNatural := make(map[secNaturalKey]uint64, len(secs))
	secByID := make(map[uint64]*model.SecurityRegistry, len(secs))
	for _, s := range secs {
		if s == nil || s.ID == 0 {
			continue
		}
		k := secNaturalKey{
			exchange:  strings.ToUpper(strings.TrimSpace(s.Exchange)),
			assetType: strings.TrimSpace(s.AssetType),
			symbol:    strings.TrimSpace(s.Symbol),
		}
		secByNatural[k] = s.ID
		secByID[s.ID] = s
	}

	catByNatural := make(map[catNaturalKey]uint64, len(cats))
	catByID := make(map[uint64]*model.TaxonomyCategory, len(cats))
	for _, cat := range cats {
		if cat == nil || cat.ID == 0 {
			continue
		}
		// catByID holds EVERY category — existence checks (CategoryExists) must succeed
		// for categories without an index_code too, since index_code is a nullable attribute,
		// not the base-table identity (source/taxonomy/market/code is).
		catByID[cat.ID] = cat
		// catByNatural (index_code → id) only covers categories that actually have an
		// resolvable index_code; the industry upsert path uses it to resolve INDEX_CODE.
		if cat.IndexCode == nil || strings.TrimSpace(*cat.IndexCode) == "" {
			continue
		}
		k := normalizeCatKey(cat.Source, cat.Taxonomy, cat.Market, *cat.IndexCode)
		catByNatural[k] = cat.ID
	}

	c.secByNatural = secByNatural
	c.secByID = secByID
	c.catByNatural = catByNatural
	c.catByID = catByID
	c.loadedAt = time.Now()
	logging.Infof(ctx, "resolve cache loaded: %d securities, %d categories", len(secByID), len(catByID))
	return nil
}

// Invalidate forces the next access to reload. Called by SecurityService on security_registry
// upsert/delete and by TaxonomyService on category upsert/delete.
func (c *ResolveCache) Invalidate() {
	c.mu.Lock()
	c.loadedAt = time.Time{}
	c.mu.Unlock()
}

// ResolveSecurityID resolves (exchange, assetType, symbol) → security_id. Returns
// (id, found, err): err is a cache/DB load failure (→ 500, not the caller's fault);
// found=false with err=nil is a genuine miss (→ 400). Callers must propagate err separately
// so a cache failure is not misreported as "id not found".
func (c *ResolveCache) ResolveSecurityID(ctx context.Context, exchange, assetType, symbol string) (uint64, bool, error) {
	if err := c.ensureLoaded(ctx); err != nil {
		return 0, false, fmt.Errorf("resolve cache unavailable: %w", err)
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	id, ok := c.secByNatural[secNaturalKey{
		exchange:  strings.ToUpper(strings.TrimSpace(exchange)),
		assetType: strings.TrimSpace(assetType),
		symbol:    strings.TrimSpace(symbol),
	}]
	return id, ok, nil
}

// ResolveCategoryID resolves (source, taxonomy, market, indexCode) → category_id, with the
// same (found, err) contract as ResolveSecurityID.
func (c *ResolveCache) ResolveCategoryID(ctx context.Context, source, taxonomy, market, indexCode string) (uint64, bool, error) {
	if err := c.ensureLoaded(ctx); err != nil {
		return 0, false, fmt.Errorf("resolve cache unavailable: %w", err)
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	id, ok := c.catByNatural[normalizeCatKey(source, taxonomy, market, indexCode)]
	return id, ok, nil
}

// ResolveSecurity returns the security row for a given id (display enrichment).
// (sec, found, err): err = load failure; found=false & err=nil = id not in cache.
func (c *ResolveCache) ResolveSecurity(ctx context.Context, id uint64) (*model.SecurityRegistry, bool, error) {
	if err := c.ensureLoaded(ctx); err != nil {
		return nil, false, fmt.Errorf("resolve cache unavailable: %w", err)
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	s, ok := c.secByID[id]
	return s, ok, nil
}

// SecurityExists reports whether a security_id is known to the cache. Returns (found, err):
// err = cache/DB load failure (→ 500); found=false & err=nil = genuine miss (→ 400). Used to
// reject orphan-id writes on the direct mapping upsert/replace endpoints (no real FK, §6 R9).
func (c *ResolveCache) SecurityExists(ctx context.Context, id uint64) (bool, error) {
	if id == 0 {
		return false, nil
	}
	_, found, err := c.ResolveSecurity(ctx, id)
	return found, err
}

// CategoryExists reports whether a category_id is known to the cache (orphan defense).
// Same (found, err) contract as SecurityExists.
func (c *ResolveCache) CategoryExists(ctx context.Context, id uint64) (bool, error) {
	if id == 0 {
		return false, nil
	}
	if err := c.ensureLoaded(ctx); err != nil {
		return false, fmt.Errorf("resolve cache unavailable: %w", err)
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	_, ok := c.catByID[id]
	return ok, nil
}

// CategoryIDsForScope resolves a (source, taxonomy, market) path to the set of category_ids
// under it. Used by SyncMappingsFromConstituents to scope the single-table SELECT. Returns
// an error if the cache could not load so the caller can distinguish a genuine empty scope
// (0 rows, ok) from a missing prerequisite / cache failure (refactor §2.3 / §10.c).
func (c *ResolveCache) CategoryIDsForScope(ctx context.Context, source, taxonomy, market string) ([]uint64, error) {
	if err := c.ensureLoaded(ctx); err != nil {
		return nil, fmt.Errorf("resolve cache unavailable: %w", err)
	}
	src := strings.TrimSpace(source)
	tax := strings.TrimSpace(taxonomy)
	mkt := strings.TrimSpace(market)
	c.mu.RLock()
	defer c.mu.RUnlock()
	ids := make([]uint64, 0)
	for k, id := range c.catByNatural {
		if k.source == src && k.taxonomy == tax && (mkt == "" || k.market == mkt) {
			ids = append(ids, id)
		}
	}
	return ids, nil
}

// resolveConCode splits a vendor code like "688526.SH" into (exchange, symbol).
// Returns ok=false if the code is not in the expected SYMBOL.EXCHANGE form.
func resolveConCode(conCode string) (exchange, symbol string, ok bool) {
	conCode = strings.TrimSpace(conCode)
	idx := strings.LastIndex(conCode, ".")
	if idx <= 0 || idx+1 >= len(conCode) {
		return "", "", false
	}
	return strings.ToUpper(conCode[idx+1:]), conCode[:idx], true
}

// resolveConstituentSecurity resolves a constituent's security_id from its ConCode
// (preferred, carries the exchange) or bare Symbol (exchange unknown → resolve fails).
// assetType is consts.ASSET_TYPE_STOCK for industry constituents. The returned error is a
// *ValidationError for client-fixable problems (bad con_code format, security not found → 400)
// or a plain wrapped error for a cache/DB load failure (→ 500). Callers wrap with %w so the
// error type is preserved through to writeServiceError.
func (c *ResolveCache) resolveConstituentSecurity(ctx context.Context, conCode, symbol string) (uint64, error) {
	if conCode == "" {
		if symbol != "" {
			return 0, NewValidationError("cannot resolve security_id from bare symbol=%q without exchange (con_code required)", symbol)
		}
		return 0, NewValidationError("empty con_code and symbol")
	}
	exchange, sym, ok := resolveConCode(conCode)
	if !ok {
		return 0, NewValidationError("con_code %q not in SYMBOL.EXCHANGE form", conCode)
	}
	id, found, err := c.ResolveSecurityID(ctx, exchange, bizConsts.ASSET_TYPE_STOCK, sym)
	if err != nil {
		return 0, fmt.Errorf("resolve security for con_code=%s: %w", conCode, err) // load failure → 500
	}
	if !found {
		return 0, NewValidationError("security not found for con_code=%s (exchange=%s symbol=%s); ensure STOCK_ZH_A_LIST has upserted it", conCode, exchange, sym)
	}
	return id, nil
}
