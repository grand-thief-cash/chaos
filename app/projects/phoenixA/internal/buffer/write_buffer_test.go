package buffer

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// ──────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────

func TestWriteBufferManager_Disabled(t *testing.T) {
	mgr := NewWriteBufferManager(Config{
		Enabled:              false,
		MaxBatchSize:         100,
		FlushInterval:        1 * time.Second,
		DirectFlushThreshold: 10,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	})

	if mgr.IsEnabled() {
		t.Error("expected buffer to be disabled")
	}
	if mgr.DirectFlushThreshold() != 10 {
		t.Errorf("expected threshold=10, got %d", mgr.DirectFlushThreshold())
	}
}

func TestWriteBufferManager_SubmitAndFlushOnInterval(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        200 * time.Millisecond,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)

	if err := mgr.Start(context.Background()); err != nil {
		t.Fatalf("start failed: %v", err)
	}

	q := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}
	bars := makeBars(5)
	err := mgr.Submit(q, bars, nil, "")
	if err != nil {
		t.Fatalf("submit failed: %v", err)
	}

	stats := mgr.Stats()
	if len(stats) != 1 {
		t.Fatalf("expected 1 buffer, got %d", len(stats))
	}
	if stats[0].SubmittedRows != 5 {
		t.Errorf("expected 5 submitted rows, got %d", stats[0].SubmittedRows)
	}
	if stats[0].Key != "bars_bars_stock_zh_a_daily_nf" {
		t.Errorf("unexpected key: %s", stats[0].Key)
	}
	if stats[0].Category != "bars" {
		t.Errorf("expected category=bars, got %s", stats[0].Category)
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_FlushOnBatchFull(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         10,
		FlushInterval:        10 * time.Second,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	q := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}

	for i := 0; i < 3; i++ {
		_ = mgr.Submit(q, makeBars(5), nil, "")
	}

	time.Sleep(50 * time.Millisecond)

	stats := mgr.Stats()
	if len(stats) == 0 {
		t.Fatal("no buffers found")
	}
	if stats[0].SubmittedRows != 15 {
		t.Errorf("expected 15 submitted, got %d", stats[0].SubmittedRows)
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_ChannelFull(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         10000,
		FlushInterval:        10 * time.Second,
		DirectFlushThreshold: 500,
		ChannelSize:          2,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	q := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}

	_ = mgr.Submit(q, makeBars(1), nil, "")
	_ = mgr.Submit(q, makeBars(1), nil, "")

	err := mgr.Submit(q, makeBars(1), nil, "")
	if err == nil {
		t.Error("expected error when channel is full")
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_ExtDataBundled(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        200 * time.Millisecond,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	q := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}
	bars := makeBars(3)
	ext := []*model.BarsExtBaostock{
		{Symbol: "000001", TradeDate: "2026-05-07", Turn: 1.23},
		{Symbol: "000002", TradeDate: "2026-05-07", Turn: 2.34},
	}
	extJSON, _ := json.Marshal(ext)

	err := mgr.Submit(q, bars, extJSON, "baostock")
	if err != nil {
		t.Fatalf("submit with ext failed: %v", err)
	}

	stats := mgr.Stats()
	if stats[0].SubmittedRows != 3 {
		t.Errorf("expected 3 submitted, got %d", stats[0].SubmittedRows)
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_MultipleKeys(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        1 * time.Second,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	q1 := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}
	q2 := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "hfq"}

	_ = mgr.Submit(q1, makeBars(3), nil, "")
	_ = mgr.Submit(q2, makeBars(7), nil, "")

	stats := mgr.Stats()
	if len(stats) != 2 {
		t.Fatalf("expected 2 buffers, got %d", len(stats))
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_IndustryWeightBuffer(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        200 * time.Millisecond,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	weights := makeIndustryWeights(5)
	err := mgr.SubmitIndustryWeights("amazing_data", "swhy", "zh_a", weights)
	if err != nil {
		t.Fatalf("submit industry weights failed: %v", err)
	}

	stats := mgr.Stats()
	if len(stats) != 1 {
		t.Fatalf("expected 1 buffer, got %d", len(stats))
	}
	if stats[0].Category != "industry_weight" {
		t.Errorf("expected category=industry_weight, got %s", stats[0].Category)
	}
	if stats[0].SubmittedRows != 5 {
		t.Errorf("expected 5 submitted, got %d", stats[0].SubmittedRows)
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_IndustryDailyBuffer(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        200 * time.Millisecond,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	daily := makeIndustryDaily(3)
	err := mgr.SubmitIndustryDaily("amazing_data", "swhy", "zh_a", daily)
	if err != nil {
		t.Fatalf("submit industry daily failed: %v", err)
	}

	stats := mgr.Stats()
	if len(stats) != 1 {
		t.Fatalf("expected 1 buffer, got %d", len(stats))
	}
	if stats[0].Category != "industry_daily" {
		t.Errorf("expected category=industry_daily, got %s", stats[0].Category)
	}

	_ = mgr.Stop(context.Background())
}

func TestWriteBufferManager_MixedBuffers(t *testing.T) {
	cfg := Config{
		Enabled:              true,
		MaxBatchSize:         100,
		FlushInterval:        1 * time.Second,
		DirectFlushThreshold: 500,
		ChannelSize:          1024,
		ShutdownTimeout:      5 * time.Second,
	}
	mgr := NewWriteBufferManager(cfg)
	_ = mgr.Start(context.Background())

	q := &model.BarsQuery{AssetType: "stock", Market: "zh_a", Period: "daily", Adjust: "nf"}
	_ = mgr.Submit(q, makeBars(3), nil, "")
	_ = mgr.SubmitIndustryWeights("amazing_data", "swhy", "zh_a", makeIndustryWeights(5))
	_ = mgr.SubmitIndustryDaily("amazing_data", "swhy", "zh_a", makeIndustryDaily(2))

	stats := mgr.Stats()
	if len(stats) != 3 {
		t.Fatalf("expected 3 buffers, got %d", len(stats))
	}

	categories := map[string]bool{}
	for _, s := range stats {
		categories[s.Category] = true
	}
	if !categories["bars"] || !categories["industry_weight"] || !categories["industry_daily"] {
		t.Errorf("missing categories in stats: %+v", stats)
	}

	_ = mgr.Stop(context.Background())
}

// ──────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────

func makeBars(n int) []*model.StandardBar {
	bars := make([]*model.StandardBar, n)
	for i := 0; i < n; i++ {
		bars[i] = &model.StandardBar{
			Symbol:    "000001",
			TradeDate: "2026-05-07",
			Open:      10.0,
			High:      11.0,
			Low:       9.0,
			Close:     10.5,
			Volume:    10000,
		}
	}
	return bars
}

func makeIndustryWeights(n int) []*model.IndustryWeight {
	weights := make([]*model.IndustryWeight, n)
	for i := 0; i < n; i++ {
		weights[i] = &model.IndustryWeight{
			IndexCode: "851426.SI",
			Symbol:    "000001",
			TradeDate: "2026-05-07",
			Weight:    0.05,
		}
	}
	return weights
}

func makeIndustryDaily(n int) []*model.IndustryDaily {
	daily := make([]*model.IndustryDaily, n)
	for i := 0; i < n; i++ {
		daily[i] = &model.IndustryDaily{
			IndexCode: "851426.SI",
			TradeDate: "2026-05-07",
			Open:      3000.0,
			Close:     3050.0,
		}
	}
	return daily
}
