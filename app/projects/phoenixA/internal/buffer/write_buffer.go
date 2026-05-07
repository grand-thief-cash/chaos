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
)

// ──────────────────────────────────────────────────────────────
// bufferEntry: a single submission (bars + optional ext)
// ──────────────────────────────────────────────────────────────

type bufferEntry struct {
	Bars []*model.StandardBar
	// ext payload kept as raw JSON + source; decoded at flush time
	ExtJSON json.RawMessage
	Source  string
}

// ──────────────────────────────────────────────────────────────
// tableBuffer: per-key channel + flush goroutine
// ──────────────────────────────────────────────────────────────

type tableBuffer struct {
	key    string // e.g. "bars_stock_zh_a_daily_nf"
	ch     chan bufferEntry
	dao    *dao.BarsDao
	q      *model.BarsQuery // template query for this key
	cfg    Config
	wg     sync.WaitGroup
	cancel context.CancelFunc

	// metrics
	submitted atomic.Int64
	flushed   atomic.Int64
	flushCnt  atomic.Int64
}

func newTableBuffer(key string, q *model.BarsQuery, barsDao *dao.BarsDao, cfg Config) *tableBuffer {
	ctx, cancel := context.WithCancel(context.Background())
	tb := &tableBuffer{
		key:    key,
		ch:     make(chan bufferEntry, cfg.ChannelSize),
		dao:    barsDao,
		q:      q,
		cfg:    cfg,
		cancel: cancel,
	}
	tb.wg.Add(1)
	go tb.loop(ctx)
	return tb
}

func (tb *tableBuffer) submit(e bufferEntry) error {
	select {
	case tb.ch <- e:
		tb.submitted.Add(int64(len(e.Bars)))
		return nil
	default:
		return fmt.Errorf("write buffer channel full for key=%s (cap=%d)", tb.key, tb.cfg.ChannelSize)
	}
}

func (tb *tableBuffer) loop(ctx context.Context) {
	defer tb.wg.Done()
	ticker := time.NewTicker(tb.cfg.FlushInterval)
	defer ticker.Stop()

	var pending []bufferEntry

	flush := func(reason string) {
		if len(pending) == 0 {
			return
		}
		tb.doFlush(pending, reason)
		pending = pending[:0] // reset slice, keep capacity
	}

	for {
		select {
		case e, ok := <-tb.ch:
			if !ok {
				// channel closed (shutdown)
				flush("shutdown_drain")
				return
			}
			pending = append(pending, e)
			if tb.pendingBarCount(pending) >= tb.cfg.MaxBatchSize {
				flush("batch_full")
			}
		case <-ticker.C:
			flush("interval")
		case <-ctx.Done():
			// drain remaining items from channel
			for {
				select {
				case e, ok := <-tb.ch:
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

func (tb *tableBuffer) pendingBarCount(entries []bufferEntry) int {
	n := 0
	for _, e := range entries {
		n += len(e.Bars)
	}
	return n
}

func (tb *tableBuffer) doFlush(entries []bufferEntry, reason string) {
	if len(entries) == 0 {
		return
	}

	// Merge all bars
	totalBars := 0
	for _, e := range entries {
		totalBars += len(e.Bars)
	}
	merged := make([]*model.StandardBar, 0, totalBars)
	for _, e := range entries {
		merged = append(merged, e.Bars...)
	}

	ctx := context.Background()

	// Flush bars
	if len(merged) > 0 && tb.dao != nil {
		if err := tb.dao.BatchUpsert(ctx, tb.q, merged); err != nil {
			logging.Errorf(ctx, "WriteBuffer flush bars failed key=%s count=%d reason=%s err=%v",
				tb.key, len(merged), reason, err)
			// TODO: retry logic or dead-letter handling
			return
		}
	}

	// Flush ext (group by source, decode and write)
	if tb.dao != nil {
		tb.flushExt(ctx, entries)
	}

	tb.flushed.Add(int64(len(merged)))
	tb.flushCnt.Add(1)

	logging.Infof(ctx, "WriteBuffer flushed key=%s bars=%d entries=%d reason=%s",
		tb.key, len(merged), len(entries), reason)
}

func (tb *tableBuffer) flushExt(ctx context.Context, entries []bufferEntry) {
	// Collect ext data by source
	type extGroup struct {
		source string
		data   []*model.BarsExtBaostock
	}
	groups := map[string]*extGroup{}

	for _, e := range entries {
		if len(e.ExtJSON) == 0 || e.Source == "" {
			continue
		}
		var ext []*model.BarsExtBaostock
		if err := json.Unmarshal(e.ExtJSON, &ext); err != nil {
			logging.Errorf(ctx, "WriteBuffer ext unmarshal failed key=%s source=%s err=%v",
				tb.key, e.Source, err)
			continue
		}
		g, ok := groups[e.Source]
		if !ok {
			g = &extGroup{source: e.Source}
			groups[e.Source] = g
		}
		g.data = append(g.data, ext...)
	}

	for _, g := range groups {
		if len(g.data) == 0 {
			continue
		}
		if err := tb.dao.BatchUpsertExt(ctx, g.source, tb.q, g.data); err != nil {
			logging.Errorf(ctx, "WriteBuffer flush ext failed key=%s source=%s count=%d err=%v",
				tb.key, g.source, len(g.data), err)
		}
	}
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
	BarsDao *dao.BarsDao `infra:"dep:dao_bars"`

	mu      sync.RWMutex
	buffers map[string]*tableBuffer
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
		buffers:       make(map[string]*tableBuffer),
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
	buffers := make([]*tableBuffer, 0, len(m.buffers))
	for _, b := range m.buffers {
		buffers = append(buffers, b)
	}
	m.mu.Unlock()

	// Signal all buffers to stop
	for _, b := range buffers {
		b.cancel()
	}

	// Wait for all buffers to flush with timeout
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

// IsEnabled returns whether the write buffer is active.
func (m *WriteBufferManager) IsEnabled() bool {
	return m.cfg.Enabled
}

// DirectFlushThreshold returns the threshold above which writes bypass the buffer.
func (m *WriteBufferManager) DirectFlushThreshold() int {
	return m.cfg.DirectFlushThreshold
}

// Submit queues bars (and optional ext) for batched writing.
// The caller should check IsEnabled() and DirectFlushThreshold() first.
func (m *WriteBufferManager) Submit(q *model.BarsQuery, bars []*model.StandardBar, extJSON json.RawMessage, source string) error {
	key := dao.BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)

	tb := m.getOrCreate(key, q)

	return tb.submit(bufferEntry{
		Bars:    bars,
		ExtJSON: extJSON,
		Source:  source,
	})
}

func (m *WriteBufferManager) getOrCreate(key string, q *model.BarsQuery) *tableBuffer {
	m.mu.RLock()
	tb, ok := m.buffers[key]
	m.mu.RUnlock()
	if ok {
		return tb
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	// double check after write lock
	if tb, ok = m.buffers[key]; ok {
		return tb
	}
	// Create a copy of the query template for this buffer
	qCopy := &model.BarsQuery{
		AssetType: q.AssetType,
		Market:    q.Market,
		Period:    q.Period,
		Adjust:    q.Adjust,
	}
	tb = newTableBuffer(key, qCopy, m.BarsDao, m.cfg)
	m.buffers[key] = tb
	return tb
}

// Stats returns current metrics for all active buffers.
func (m *WriteBufferManager) Stats() []BufferStats {
	m.mu.RLock()
	defer m.mu.RUnlock()
	stats := make([]BufferStats, 0, len(m.buffers))
	for _, tb := range m.buffers {
		stats = append(stats, BufferStats{
			Key:           tb.key,
			SubmittedRows: tb.submitted.Load(),
			FlushedRows:   tb.flushed.Load(),
			PendingItems:  len(tb.ch),
			FlushCount:    tb.flushCnt.Load(),
		})
	}
	return stats
}
