package service

import (
	"context"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
)

type RunCleanupService struct {
	*core.BaseComponent
	RunDao dao.RunDao `infra:"dep:run_dao"`
	cfg    config.CleanupConfig
	cancel context.CancelFunc
}

func NewRunCleanupService(cfg config.CleanupConfig) *RunCleanupService {
	return &RunCleanupService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_RUN_CLEANUP), cfg: cfg}
}

func (s *RunCleanupService) Start(ctx context.Context) error {
	if err := s.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if !s.cfg.Enabled {
		return nil
	}
	loopCtx, cancel := context.WithCancel(context.Background())
	s.cancel = cancel
	interval := s.cfg.Interval
	if interval <= 0 {
		interval = time.Hour
	}
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-loopCtx.Done():
				return
			case <-ticker.C:
				s.autoCleanup(loopCtx)
			}
		}
	}()
	return nil
}

func (s *RunCleanupService) Stop(ctx context.Context) error {
	if s.cancel != nil {
		s.cancel()
	}
	return s.BaseComponent.Stop(ctx)
}

// Summary returns counts per task (limited naive implementation)
func (s *RunCleanupService) Summary(ctx context.Context, limit int) (map[int64]int, error) {
	return s.RunDao.CountPerTask(ctx, limit)
}

// CleanupByAge deletes runs older than maxAge (optionally scoped to taskID if >0)
func (s *RunCleanupService) CleanupByAge(ctx context.Context, taskID int64, maxAge time.Duration) (int64, error) {
	if maxAge <= 0 {
		return 0, fmt.Errorf("invalid maxAge")
	}
	deadline := time.Now().Add(-maxAge)
	return s.RunDao.DeleteOlderThan(ctx, taskID, deadline)
}

// CleanupByKeep deletes older runs keeping only the most recent 'keep' runs for a task (taskID>0) or all tasks (loop)
func (s *RunCleanupService) CleanupByKeep(ctx context.Context, taskID int64, keep int) (int64, error) {
	if keep < 0 {
		return 0, fmt.Errorf("invalid keep")
	}
	if taskID > 0 { // single task chunked
		return s.CleanupByKeepChunked(ctx, taskID, keep, 500)
	}
	// global: iterate tasks and chunk each
	counts, err := s.Summary(ctx, 100000)
	if err != nil {
		return 0, err
	}
	var total int64
	for tid, cnt := range counts {
		if cnt <= keep {
			continue
		}
		deleted, _ := s.CleanupByKeepChunked(ctx, tid, keep, 500)
		total += deleted
	}
	return total, nil
}

// CleanupByIDs deletes specified run IDs
func (s *RunCleanupService) CleanupByIDs(ctx context.Context, ids []int64) (int64, error) {
	if len(ids) == 0 {
		return 0, nil
	}
	return s.RunDao.DeleteByIDs(ctx, ids)
}

// autoCleanup executes configured cleanup policies
func (s *RunCleanupService) autoCleanup(ctx context.Context) {
	if s.cfg.MaxAge > 0 {
		deleted, err := s.CleanupByAge(ctx, 0, s.cfg.MaxAge)
		if err != nil {
			logging.Error(ctx, "auto cleanup age err: "+err.Error())
		} else {
			logging.Info(ctx, fmt.Sprintf("auto cleanup age deleted=%d", deleted))
		}
	}
	if s.cfg.MaxPerTask > 0 {
		counts, err := s.Summary(ctx, 10000)
		if err != nil {
			logging.Error(ctx, "summary for keep failed: "+err.Error())
			return
		}
		var totalDeleted int64
		for taskID, cnt := range counts {
			if cnt <= s.cfg.MaxPerTask {
				continue
			}
			deleted, _ := s.CleanupByKeepChunked(ctx, taskID, s.cfg.MaxPerTask, 500)
			totalDeleted += deleted
		}
		logging.Info(ctx, fmt.Sprintf("auto cleanup keep per task totalDeleted=%d", totalDeleted))
	}
}

// CleanupByKeepChunked deletes older runs keeping only the most recent 'keep' runs using chunk batches.
func (s *RunCleanupService) CleanupByKeepChunked(ctx context.Context, taskID int64, keep, chunk int) (int64, error) {
	if keep < 0 {
		return 0, fmt.Errorf("invalid keep")
	}
	if chunk <= 0 {
		chunk = 500
	}
	// list ids beyond keep in batches
	var totalDeleted int64
	for {
		ids, err := s.RunDao.ListIDsOffset(ctx, taskID, keep, chunk) // new helper; will add
		if err != nil {
			return totalDeleted, err
		}
		if len(ids) == 0 {
			break
		}
		deleted, err2 := s.RunDao.DeleteByIDs(ctx, ids)
		if err2 != nil {
			return totalDeleted, err2
		}
		totalDeleted += deleted
		if len(ids) < chunk {
			break
		}
		// small throttle
		time.Sleep(50 * time.Millisecond)
	}
	return totalDeleted, nil
}
