package service

import (
	"context"
	"sort"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/cache"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// Two-level cache for the security registry search hot path.
//
// The registry is small (~5k A-shares per scope) and rarely changes, but the
// typeahead is high-frequency. Reading the full list from Redis on every
// keystroke would still pay a ~1MB network transfer + full JSON unmarshal
// each time. L1 keeps the already-deserialized slice in process memory so a
// search is a pure in-memory filter; L2 (Redis, 6h) is shared across replicas
// and survives restarts; DB is the cold source.
//
//   request -> L1 (process-local, deserialized, TTL securitySnapshotTTL)
//                 | miss
//                 v
//              L2 (Redis security:list:{asset_type}:{market}, 6h)
//                 | miss / Redis down
//                 v
//              DB (full scope load) -> backfill L2 + L1
//
// Cross-replica staleness is bounded by securitySnapshotTTL (v1 SLA: other
// replicas converge within the TTL after an upsert/delete; Redis Pub/Sub can
// make it immediate later). Singleflight dedupes concurrent cold loads of the
// same scope so a burst does not fan out N DB queries.

const securitySnapshotTTL = 30 * time.Second

// securitySnapshot is an L1 entry: the full deserialized registry slice for
// one (asset_type, market) scope plus its load time. Callers must treat the
// contained pointers as read-only - mutating them would corrupt the cache.
type securitySnapshot struct {
	list     []*model.SecurityRegistry
	loadedAt time.Time
}

func (s *securitySnapshot) fresh() bool {
	return s != nil && !s.loadedAt.IsZero() && time.Since(s.loadedAt) < securitySnapshotTTL
}

// snapshotCall dedupes concurrent cold loads of one scope (singleflight). The
// first caller loads; concurrent callers wait on done and reuse the result.
type snapshotCall struct {
	done chan struct{}
	snap *securitySnapshot
	err  error
}

// SecuritySearchResult is the one-pass search response: items + total +
// pagination, all computed over a single L1 snapshot so list and count cannot
// diverge (the old list-then-count path had an inconsistency window).
type SecuritySearchResult struct {
	Items  []*model.SecurityRegistry `json:"items"`
	Total  int64                     `json:"total"`
	Limit  int                       `json:"limit"`
	Offset int                       `json:"offset"`
}

// SearchPage filters + sorts + paginates the registry over one L1 snapshot.
// q (symbol exact case-insensitive OR name contains) is the unified search
// term; legacy Symbol/Name/Exchange/Status filters are also honored in memory.
// On snapshot failure (DB down) it degrades to a DAO query with Q - the
// documented non-snapshot fallback.
func (s *SecurityService) SearchPage(ctx context.Context, f *model.SecurityFilters, limit, offset int) (*SecuritySearchResult, error) {
	assetType, market := normalizeSecurityAggregateScope("", "")
	if f != nil {
		assetType, market = normalizeSecurityAggregateScope(f.AssetType, f.Market)
	}
	scope := scopeKey(assetType, market)
	searchStart := time.Now()

	snap, err := s.loadSnapshot(ctx, assetType, market, scope)
	if err != nil || snap == nil {
		// Degraded path: snapshot unavailable -> DAO with Q. total needs a
		// second DAO call only here; the happy path computes total in memory.
		logging.Warnf(ctx, "security search snapshot fallback to dao scope=%s err=%v", scope, err)
		list, lerr := s.Dao.ListFiltered(ctx, f, limit, offset)
		if lerr != nil {
			return nil, lerr
		}
		cnt, cerr := s.Dao.CountFiltered(ctx, f)
		if cerr != nil {
			return nil, cerr
		}
		logging.Infof(ctx, "security search event=dao_fallback scope=%s total=%d search_ms=%d",
			scope, cnt, time.Since(searchStart).Milliseconds())
		return &SecuritySearchResult{Items: list, Total: cnt, Limit: limit, Offset: offset}, nil
	}

	filtered, total := searchOverSnapshot(snap.list, f, limit, offset)
	// Per-query logging is intentionally omitted: the typeahead is high-
	// frequency and L1 hits are the common case. Snapshot-load events (L2 hit,
	// DB load, fallback) are logged where they happen - those are rare.
	return &SecuritySearchResult{Items: filtered, Total: total, Limit: limit, Offset: offset}, nil
}

// searchOverSnapshot applies the q / legacy filters + sort + pagination to a
// cached snapshot slice and returns (page, total). Pure (no I/O) so the q
// semantics, sort order, total, and pagination consistency are unit-testable
// independent of the DAO / Redis.
func searchOverSnapshot(list []*model.SecurityRegistry, f *model.SecurityFilters, limit, offset int) ([]*model.SecurityRegistry, int64) {
	filtered := filterSecurityList(list, f)
	total := int64(len(filtered))

	// Sort: exact-symbol (case-insensitive) tier first, each tier symbol ASC.
	// With empty Q this degenerates to plain symbol ASC, matching the DAO order.
	sort.SliceStable(filtered, func(i, j int) bool {
		return securityLess(filtered[i], filtered[j], f)
	})

	if offset < 0 {
		offset = 0
	}
	if offset > len(filtered) {
		offset = len(filtered)
	}
	end := len(filtered)
	if limit > 0 && offset+limit < end {
		end = offset + limit
	}
	return filtered[offset:end], total
}

// loadSnapshot returns a fresh L1 snapshot for the scope, populating L1 from
// L2 (Redis) on a miss and from DB on an L2 miss, with singleflight deduping.
// If Redis is unavailable the DB result is still cached in L1 so a Redis
// outage does not turn every query into a DB hit.
func (s *SecurityService) loadSnapshot(ctx context.Context, assetType, market, scope string) (*securitySnapshot, error) {
	// L1 fast path.
	s.l1Mu.RLock()
	snap, ok := s.l1[scope]
	s.l1Mu.RUnlock()
	if ok && snap.fresh() {
		return snap, nil
	}

	// Singleflight: only one caller loads a given scope at a time. Concurrent
	// callers find the in-flight call and wait on its done channel.
	s.inflightMu.Lock()
	if call, exists := s.inflight[scope]; exists {
		s.inflightMu.Unlock()
		<-call.done
		return call.snap, call.err
	}
	call := &snapshotCall{done: make(chan struct{})}
	s.inflight[scope] = call
	s.inflightMu.Unlock()

	// We own the load.
	snap2, err := s.loadSnapshotFromL2OrDB(ctx, assetType, market, scope)
	if snap2 != nil {
		s.l1Mu.Lock()
		s.l1[scope] = snap2
		s.l1Mu.Unlock()
	}
	// Publish result to waiters before returning. snap/err are set before
	// close(done) so waiters waking on <-done observe them (happens-before).
	call.snap = snap2
	call.err = err
	s.inflightMu.Lock()
	delete(s.inflight, scope)
	s.inflightMu.Unlock()
	close(call.done)
	return snap2, err
}

func (s *SecurityService) loadSnapshotFromL2OrDB(ctx context.Context, assetType, market, scope string) (*securitySnapshot, error) {
	client := s.redisClient()
	key := bizConsts.BuildSecurityListCacheKey(assetType, market)

	// L2 (Redis).
	if client != nil {
		l2Start := time.Now()
		if cached, hit, err := cache.GetJSON[[]*model.SecurityRegistry](ctx, client, key); err == nil && hit {
			logging.Infof(ctx, "security snapshot event=cache_hit source=l2 scope=%s size=%d load_ms=%d",
				scope, len(cached), time.Since(l2Start).Milliseconds())
			return &securitySnapshot{list: cached, loadedAt: time.Now()}, nil
		} else if err != nil {
			logging.Warnf(ctx, "security snapshot l2 get failed scope=%s err=%v", scope, err)
		}
	}

	// L2 miss or Redis down -> DB full load.
	dbStart := time.Now()
	list, err := s.Dao.ListFiltered(ctx, &model.SecurityFilters{AssetType: assetType, Market: market}, 0, 0)
	if err != nil {
		return nil, err
	}
	logging.Infof(ctx, "security snapshot event=db_load scope=%s size=%d load_ms=%d",
		scope, len(list), time.Since(dbStart).Milliseconds())

	// Backfill L2 (best-effort). Skipped when Redis is down; L1 still gets it.
	if client != nil {
		if err := cache.SetJSON(ctx, client, key, time.Duration(bizConsts.RedisCacheTTLSecondsSecurityList)*time.Second, list); err != nil {
			logging.Warnf(ctx, "security snapshot l2 set failed scope=%s err=%v", scope, err)
		}
	}
	return &securitySnapshot{list: list, loadedAt: time.Now()}, nil
}

// invalidateL1 clears every scope's process-local snapshot. Called on any
// registry upsert - the other replicas' L1 converges via TTL (v1 SLA).
func (s *SecurityService) invalidateL1() {
	s.l1Mu.Lock()
	s.l1 = make(map[string]*securitySnapshot)
	s.l1Mu.Unlock()
}

// filterSecurityList applies the SecurityFilters to the cached slice in memory.
// It returns a NEW slice (subsetting pointers); the cached slice/order is never
// mutated. Semantics mirror applySecurityFilters in the DAO so the snapshot
// path and the DAO fallback return the same rows for the same filter.
func filterSecurityList(list []*model.SecurityRegistry, f *model.SecurityFilters) []*model.SecurityRegistry {
	out := make([]*model.SecurityRegistry, 0, len(list))
	if f == nil {
		out = append(out, list...)
		return out
	}

	q := strings.TrimSpace(f.Q)
	qExchanges := make(map[string]struct{}, len(f.Exchanges))
	for _, e := range f.Exchanges {
		e = strings.ToUpper(strings.TrimSpace(e))
		if e != "" {
			qExchanges[e] = struct{}{}
		}
	}
	exchangeSingle := strings.ToUpper(strings.TrimSpace(f.Exchange))
	symbolSet := make(map[string]struct{}, len(f.Symbols))
	for _, sym := range f.Symbols {
		symbolSet[strings.TrimSpace(sym)] = struct{}{}
	}
	nameNeedle := strings.TrimSpace(f.Name)

	for _, s := range list {
		if s == nil {
			continue
		}
		if f.SecurityID != 0 && s.ID != f.SecurityID {
			continue
		}
		if f.Symbol != "" && strings.TrimSpace(s.Symbol) != strings.TrimSpace(f.Symbol) {
			continue
		}
		if len(symbolSet) > 0 {
			if _, ok := symbolSet[strings.TrimSpace(s.Symbol)]; !ok {
				continue
			}
		}
		if exchangeSingle != "" && strings.ToUpper(s.Exchange) != exchangeSingle {
			continue
		}
		if len(qExchanges) > 0 {
			if _, ok := qExchanges[strings.ToUpper(s.Exchange)]; !ok {
				continue
			}
		}
		if f.Status != "" && s.Status != f.Status {
			continue
		}
		if nameNeedle != "" && !strings.Contains(s.Name, nameNeedle) {
			continue
		}
		// Q: symbol exact (case-insensitive) OR name contains (case-sensitive).
		if q != "" && !strings.EqualFold(s.Symbol, q) && !strings.Contains(s.Name, q) {
			continue
		}
		out = append(out, s)
	}
	return out
}

// securityLess is the sort comparator: exact-symbol tier first (so q=000001
// surfaces the exact symbol before name-fuzzy matches), each tier symbol ASC.
func securityLess(a, b *model.SecurityRegistry, f *model.SecurityFilters) bool {
	q := ""
	if f != nil {
		q = strings.TrimSpace(f.Q)
	}
	if q != "" {
		aExact := strings.EqualFold(a.Symbol, q)
		bExact := strings.EqualFold(b.Symbol, q)
		if aExact != bExact {
			return aExact
		}
	}
	return a.Symbol < b.Symbol
}

func scopeKey(assetType, market string) string {
	a, m := normalizeSecurityAggregateScope(assetType, market)
	return a + ":" + m
}
