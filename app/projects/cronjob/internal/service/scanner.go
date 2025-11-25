package service

import (
	"context"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// RunScanner: unified periodic scanner
// Responsibilities:
// 1. Callback timeout: mark CALLBACK_PENDING runs whose callback_deadline passed as FAILED_TIMEOUT.
// 2. Stuck sync runs: mark RUNNING SYNC runs whose start_time exceeds configured stuck timeout & updated_at also old.
// 3. Progress cleanup: clear in-memory progress for terminal runs after grace period.
// Avoid heavy DB pressure by batching operations.

type RunScanner struct {
	*core.BaseComponent
	RunSvc     *RunService         `infra:"dep:run_service"`
	Progress   *RunProgressManager `infra:"dep:run_progress_mgr"`
	interval   time.Duration
	batchLimit int
	cancel     context.CancelFunc
	cfg        config.ScannerConfig
}

func NewRunScanner(cfg config.ScannerConfig) *RunScanner {
	interval := cfg.Interval
	if interval <= 0 {
		interval = 30 * time.Second
	}
	batch := cfg.BatchLimit
	if batch <= 0 {
		batch = 500
	}
	return &RunScanner{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_CALLBACK_SCANNER), interval: interval, batchLimit: batch, cfg: cfg}
}

func (s *RunScanner) Start(ctx context.Context) error {
	if s.IsActive() {
		return nil
	}
	if err := s.BaseComponent.Start(ctx); err != nil {
		return err
	}
	loopCtx, cancel := context.WithCancel(context.Background())
	s.cancel = cancel
	go s.loop(loopCtx)
	return nil
}

func (s *RunScanner) Stop(ctx context.Context) error {
	if !s.IsActive() {
		return nil
	}
	if s.cancel != nil {
		s.cancel()
	}
	return s.BaseComponent.Stop(ctx)
}

func (s *RunScanner) loop(ctx context.Context) {
	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.tick(ctx)
		}
	}
}

func (s *RunScanner) tick(ctx context.Context) {
	s.scanCallbackTimeouts(ctx)
	s.scanStuckSync(ctx)
	s.cleanupProgress(ctx)
}

// scanCallbackTimeouts marks expired callback deadlines.
func (s *RunScanner) scanCallbackTimeouts(ctx context.Context) {
	expired, err := s.RunSvc.ListCallbackPendingExpired(ctx, s.batchLimit)
	if err != nil {
		logging.Error(ctx, "run_scanner list expired failed: "+err.Error())
		return
	}
	for _, run := range expired {
		if err := s.RunSvc.MarkFailedTimeout(ctx, run.ID, "callback_deadline_exceeded"); err != nil {
			logging.Error(ctx, "mark failed timeout run="+err.Error())
			continue
		}
		logging.Info(ctx, fmt.Sprintf("callback deadline exceeded run_id=%d", run.ID))
	}
}

// scanStuckSync detects RUNNING SYNC runs older than configured threshold.
func (s *RunScanner) scanStuckSync(ctx context.Context) {
	toSec := s.cfg.SyncRunStuckTimeoutSeconds
	if toSec <= 0 {
		return
	} // disabled
	startCutoff := time.Now().Add(-time.Duration(toSec) * time.Second)
	// Use same cutoff for updated_at to ensure no recent activity
	updatedCutoff := startCutoff
	list, err := s.RunSvc.ListSyncRunningStuck(ctx, startCutoff, updatedCutoff, s.batchLimit)
	if err != nil {
		logging.Error(ctx, "run_scanner list stuck sync failed: "+err.Error())
		return
	}
	for _, run := range list {
		if err := s.RunSvc.MarkTimeout(ctx, run.ID, "sync_run_stuck_timeout"); err != nil {
			logging.Error(ctx, fmt.Sprintf("mark sync stuck timeout failed id=%d err=%v", run.ID, err))
			continue
		}
		logging.Warn(ctx, fmt.Sprintf("sync run stuck marked timeout id=%d", run.ID))
	}
}

// cleanupProgress clears progress entries for terminal runs after grace.
func (s *RunScanner) cleanupProgress(ctx context.Context) {
	if s.Progress == nil {
		return
	}
	graceSec := s.cfg.ProgressCleanupGraceSeconds
	grace := time.Duration(graceSec) * time.Second
	entries := s.Progress.List()
	if len(entries) == 0 {
		return
	}
	// Collect run IDs
	ids := make([]int64, 0, len(entries))
	for _, p := range entries {
		ids = append(ids, p.RunID)
	}
	// Batch fetch statuses (limit batches to avoid huge IN clauses)
	batchSize := 500
	terminal := map[bizConsts.RunStatus]struct{}{bizConsts.Success: {}, bizConsts.Failed: {}, bizConsts.FailedTimeout: {}, bizConsts.Timeout: {}, bizConsts.Canceled: {}, bizConsts.Skipped: {}, bizConsts.FailureSkip: {}, bizConsts.ConcurrentSkip: {}, bizConsts.OverlapSkip: {}, bizConsts.CallbackFailed: {}}
	now := time.Now()
	for i := 0; i < len(ids); i += batchSize {
		end := i + batchSize
		if end > len(ids) {
			end = len(ids)
		}
		chunk := ids[i:end]
		runs, err := s.RunSvc.ListByIDs(ctx, chunk)
		if err != nil {
			logging.Error(ctx, "listByIDs failed: "+err.Error())
			continue
		}
		for _, r := range runs {
			if _, ok := terminal[r.Status]; !ok {
				continue
			}
			if graceSec > 0 && r.EndTime != nil && now.Sub(*r.EndTime) < grace {
				continue
			}
			s.Progress.Clear(r.ID)
			logging.Debug(ctx, fmt.Sprintf("progress cleared run_id=%d status=%s", r.ID, r.Status))
		}
	}
}
