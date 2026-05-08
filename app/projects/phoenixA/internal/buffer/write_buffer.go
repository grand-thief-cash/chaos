package buffer

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"

	legacyDao "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

// ──────────────────────────────────────────────────────────────
// genericEntry: a single submission carrying any business data
// ──────────────────────────────────────────────────────────────

type genericEntry struct {
	Data  interface{} // the typed payload (bars, weights, daily, etc.)
	Count int         // row count for this entry
}

// FlushFunc processes accumulated entries for a specific buffer key.
// Returns the total number of rows flushed.
type FlushFunc func(ctx context.Context, key string, entries []genericEntry) (int, error)

// ──────────────────────────────────────────────────────────────
// barsEntry: bars-specific payload (backward compatible)
// ──────────────────────────────────────────────────────────────

type barsEntry struct {
	Bars    []*model.StandardBar
	ExtJSON json.RawMessage
	Source  string
	Query   *model.BarsQuery // captured for ext flush
}

// ──────────────────────────────────────────────────────────────
// genericBuffer: per-key channel + flush goroutine
// ──────────────────────────────────────────────────────────────

type genericBuffer struct {
	key       string // e.g. "bars_stock_zh_a_daily_nf" or "industry_weight_amazing_data_swhy_zh_a"
	category  string // business category: "bars", "industry_weight", "industry_daily", etc.
	ch        chan genericEntry
	flushFunc FlushFunc
	cfg       Config
	wg        sync.WaitGroup
	cancel    context.CancelFunc

	submitted atomic.Int64
	flushed   atomic.Int64
	flushCnt  atomic.Int64
}

func newGenericBuffer(key, category string, flushFunc FlushFunc, cfg Config) *genericBuffer {
	ctx, cancel := context.WithCancel(context.Background())
	b := &genericBuffer{
		key:       key,
		category:  category,
		ch:        make(chan genericEntry, cfg.ChannelSize),
		flushFunc: flushFunc,
		cfg:       cfg,
		cancel:    cancel,
	}
	b.wg.Add(1)
	go b.loop(ctx)
	return b
}

func (b *genericBuffer) submit(e genericEntry) error {
	select {
	case b.ch <- e:
		b.submitted.Add(int64(e.Count))
		return nil
	default:
		return fmt.Errorf("write buffer channel full for key=%s (cap=%d)", b.key, b.cfg.ChannelSize)
	}
}

func (b *genericBuffer) loop(ctx context.Context) {
	defer b.wg.Done()
	ticker := time.NewTicker(b.cfg.FlushInterval)
	defer ticker.Stop()

	var pending []genericEntry

	flush := func(reason string) {
		if len(pending) == 0 {
			return
		}
		b.doFlush(pending, reason)
		pending = pending[:0]
	}

	for {
		select {
		case e, ok := <-b.ch:
			if !ok {
				flush("shutdown_drain")
				return
			}
			pending = append(pending, e)
			if b.pendingCount(pending) >= b.cfg.MaxBatchSize {
				flush("batch_full")
			}
		case <-ticker.C:
			flush("interval")
		case <-ctx.Done():
			for {
				select {
				case e, ok := <-b.ch:
					if !ok {
						flush("shutdown_final")
						return
					}
					pending = append(pending, e)
				default:
					flush("shutdown_ctx")
					return
				}
			}
		}
	}
}

func (b *genericBuffer) pendingCount(entries []genericEntry) int {
	n := 0
	for _, e := range entries {
		n += e.Count
	}
	return n
}

func (b *genericBuffer) doFlush(entries []genericEntry, reason string) {
	if len(entries) == 0 {
		return
	}

	ctx := context.Background()
	total, err := b.flushFunc(ctx, b.key, entries)
	if err != nil {
		logging.Errorf(ctx, "WriteBuffer flush failed key=%s entries=%d reason=%s err=%v",
			b.key, len(entries), reason, err)
		return
	}

	b.flushed.Add(int64(total))
	b.flushCnt.Add(1)

	logging.Infof(ctx, "WriteBuffer flushed key=%s rows=%d entries=%d reason=%s",
		b.key, total, len(entries), reason)
}

// ──────────────────────────────────────────────────────────────
// Config mirrors the YAML structure
// ──────────────────────────────────────────────────────────────

type Config struct {
	Enabled              bool
	MaxBatchSize         int
	FlushInterval        time.Duration
	DirectFlushThreshold int
	ChannelSize          int
	ShutdownTimeout      time.Duration
}

// ──────────────────────────────────────────────────────────────
// Stats for observability
// ──────────────────────────────────────────────────────────────

type BufferStats struct {
	Key           string `json:"key"`
	Category      string `json:"category"`
	SubmittedRows int64  `json:"submitted_rows"`
	FlushedRows   int64  `json:"flushed_rows"`
	PendingItems  int    `json:"pending_items"`
	FlushCount    int64  `json:"flush_count"`
}

// ──────────────────────────────────────────────────────────────
// WriteBufferManager: lifecycle component
// ──────────────────────────────────────────────────────────────

type WriteBufferManager struct {
	*core.BaseComponent
	BarsDao     *legacyDao.BarsDao     `infra:"dep:dao_bars"`
	TaxonomyDao *legacyDao.TaxonomyDao `infra:"dep:dao_taxonomy"`

	mu      sync.RWMutex
	buffers map[string]*genericBuffer
	cfg     Config
}

func NewWriteBufferManager(cfg Config) *WriteBufferManager {
	if cfg.MaxBatchSize <= 0 {
		cfg.MaxBatchSize = 2000
	}
	if cfg.FlushInterval <= 0 {
		cfg.FlushInterval = 3 * time.Second
	}
	if cfg.DirectFlushThreshold <= 0 {
		cfg.DirectFlushThreshold = 500
	}
	if cfg.ChannelSize <= 0 {
		cfg.ChannelSize = 8192
	}
	if cfg.ShutdownTimeout <= 0 {
		cfg.ShutdownTimeout = 10 * time.Second
	}
	return &WriteBufferManager{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_WRITE_BUFFER, consts.COMPONENT_LOGGING),
		buffers:       make(map[string]*genericBuffer),
		cfg:           cfg,
	}
}

func (m *WriteBufferManager) Start(ctx context.Context) error {
	if !m.cfg.Enabled {
		logging.Info(ctx, "WriteBufferManager disabled, all writes go direct path")
	} else {
		logging.Infof(ctx, "WriteBufferManager started: max_batch=%d flush_interval=%s direct_threshold=%d",
			m.cfg.MaxBatchSize, m.cfg.FlushInterval, m.cfg.DirectFlushThreshold)
	}
	return m.BaseComponent.Start(ctx)
}

func (m *WriteBufferManager) Stop(ctx context.Context) error {
	m.mu.Lock()
	buffers := make([]*genericBuffer, 0, len(m.buffers))
	for _, b := range m.buffers {
		buffers = append(buffers, b)
	}
	m.mu.Unlock()

	for _, b := range buffers {
		b.cancel()
	}

	done := make(chan struct{})
	go func() {
		for _, b := range buffers {
			b.wg.Wait()
		}
		close(done)
	}()

	select {
	case <-done:
		logging.Infof(ctx, "WriteBufferManager: all %d buffers flushed on shutdown", len(buffers))
	case <-time.After(m.cfg.ShutdownTimeout):
		logging.Warnf(ctx, "WriteBufferManager: shutdown timeout after %s, some data may be lost", m.cfg.ShutdownTimeout)
	}

	return m.BaseComponent.Stop(ctx)
}

func (m *WriteBufferManager) IsEnabled() bool {
	return m.cfg.Enabled
}

func (m *WriteBufferManager) DirectFlushThreshold() int {
	return m.cfg.DirectFlushThreshold
}

// ──────────── Bars submit (backward compatible) ────────────

func (m *WriteBufferManager) Submit(q *model.BarsQuery, bars []*model.StandardBar, extJSON json.RawMessage, source string) error {
	key := "bars_" + dao.BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	buf := m.getOrCreate(key, "bars", m.barsFlushFunc())
	return buf.submit(genericEntry{
		Data: barsEntry{
			Bars:    bars,
			ExtJSON: extJSON,
			Source:  source,
			Query:   q,
		},
		Count: len(bars),
	})
}

func (m *WriteBufferManager) barsFlushFunc() FlushFunc {
	return func(ctx context.Context, key string, entries []genericEntry) (int, error) {
		var allBars []*model.StandardBar
		var firstQuery *model.BarsQuery
		for _, e := range entries {
			be, ok := e.Data.(barsEntry)
			if !ok {
				continue
			}
			allBars = append(allBars, be.Bars...)
			if firstQuery == nil && be.Query != nil {
				qCopy := *be.Query
				firstQuery = &qCopy
			}
		}
		if len(allBars) == 0 {
			return 0, nil
		}
		if m.BarsDao == nil {
			return 0, fmt.Errorf("BarsDao is nil")
		}
		if err := m.BarsDao.BatchUpsert(ctx, firstQuery, allBars); err != nil {
			return 0, err
		}
		// Flush ext data
		m.flushBarsExt(ctx, entries, firstQuery)
		return len(allBars), nil
	}
}

func (m *WriteBufferManager) flushBarsExt(ctx context.Context, entries []genericEntry, q *model.BarsQuery) {
	type extGroup struct {
		source string
		data   []*model.BarsExtBaostock
	}
	groups := map[string]*extGroup{}

	for _, e := range entries {
		be, ok := e.Data.(barsEntry)
		if !ok || len(be.ExtJSON) == 0 || be.Source == "" {
			continue
		}
		var ext []*model.BarsExtBaostock
		if err := json.Unmarshal(be.ExtJSON, &ext); err != nil {
			logging.Errorf(ctx, "WriteBuffer ext unmarshal failed source=%s err=%v", be.Source, err)
			continue
		}
		g, ok := groups[be.Source]
		if !ok {
			g = &extGroup{source: be.Source}
			groups[be.Source] = g
		}
		g.data = append(g.data, ext...)
	}

	if q == nil || m.BarsDao == nil {
		return
	}
	for _, g := range groups {
		if len(g.data) == 0 {
			continue
		}
		if err := m.BarsDao.BatchUpsertExt(ctx, g.source, q, g.data); err != nil {
			logging.Errorf(ctx, "WriteBuffer flush ext failed source=%s count=%d err=%v",
				g.source, len(g.data), err)
		}
	}
}

// ──────────── Industry Weight submit ────────────

func (m *WriteBufferManager) SubmitIndustryWeights(source, taxonomy, market string, weights []*model.IndustryWeight) error {
	key := fmt.Sprintf("industry_weight_%s_%s_%s", source, taxonomy, market)
	buf := m.getOrCreate(key, "industry_weight", m.industryWeightsFlushFunc(source, taxonomy, market))
	return buf.submit(genericEntry{
		Data:  weights,
		Count: len(weights),
	})
}

func (m *WriteBufferManager) industryWeightsFlushFunc(source, taxonomy, market string) FlushFunc {
	return func(ctx context.Context, key string, entries []genericEntry) (int, error) {
		var all []*model.IndustryWeight
		for _, e := range entries {
			weights, ok := e.Data.([]*model.IndustryWeight)
			if !ok {
				continue
			}
			all = append(all, weights...)
		}
		if len(all) == 0 {
			return 0, nil
		}
		if m.TaxonomyDao == nil {
			return 0, fmt.Errorf("TaxonomyDao is nil")
		}
		if err := m.TaxonomyDao.BatchUpsertWeights(ctx, source, taxonomy, market, all); err != nil {
			return 0, err
		}
		return len(all), nil
	}
}

// ──────────── Industry Daily submit ────────────

func (m *WriteBufferManager) SubmitIndustryDaily(source, taxonomy, market string, daily []*model.IndustryDaily) error {
	key := fmt.Sprintf("industry_daily_%s_%s_%s", source, taxonomy, market)
	buf := m.getOrCreate(key, "industry_daily", m.industryDailyFlushFunc(source, taxonomy, market))
	return buf.submit(genericEntry{
		Data:  daily,
		Count: len(daily),
	})
}

func (m *WriteBufferManager) industryDailyFlushFunc(source, taxonomy, market string) FlushFunc {
	return func(ctx context.Context, key string, entries []genericEntry) (int, error) {
		var all []*model.IndustryDaily
		for _, e := range entries {
			daily, ok := e.Data.([]*model.IndustryDaily)
			if !ok {
				continue
			}
			all = append(all, daily...)
		}
		if len(all) == 0 {
			return 0, nil
		}
		if m.TaxonomyDao == nil {
			return 0, fmt.Errorf("TaxonomyDao is nil")
		}
		if err := m.TaxonomyDao.BatchUpsertIndustryDaily(ctx, source, taxonomy, market, all); err != nil {
			return 0, err
		}
		return len(all), nil
	}
}

// ──────────── Generic helpers ────────────

func (m *WriteBufferManager) getOrCreate(key, category string, flushFunc FlushFunc) *genericBuffer {
	m.mu.RLock()
	b, ok := m.buffers[key]
	m.mu.RUnlock()
	if ok {
		return b
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	if b, ok = m.buffers[key]; ok {
		return b
	}
	b = newGenericBuffer(key, category, flushFunc, m.cfg)
	m.buffers[key] = b
	return b
}

// Stats returns current metrics for all active buffers.
func (m *WriteBufferManager) Stats() []BufferStats {
	m.mu.RLock()
	defer m.mu.RUnlock()
	stats := make([]BufferStats, 0, len(m.buffers))
	for _, b := range m.buffers {
		stats = append(stats, BufferStats{
			Key:           b.key,
			Category:      b.category,
			SubmittedRows: b.submitted.Load(),
			FlushedRows:   b.flushed.Load(),
			PendingItems:  len(b.ch),
			FlushCount:    b.flushCnt.Load(),
		})
	}
	return stats
}
