package service

import (
	"context"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// RunProgressManager stores ephemeral progress info per run.
type RunProgressManager struct {
	*core.BaseComponent
	mu   sync.RWMutex
	data map[int64]*RunProgress
}

type RunProgress struct {
	RunID   int64     `json:"run_id"`
	Current int64     `json:"current"`
	Total   int64     `json:"total"`
	Percent int       `json:"percent"`
	Message string    `json:"message"`
	Updated time.Time `json:"updated_at"`
}

func NewRunProgressManager() *RunProgressManager {
	return &RunProgressManager{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_RUN_PROGRESS), data: make(map[int64]*RunProgress)}
}

func (rpm *RunProgressManager) Start(ctx context.Context) error { return rpm.BaseComponent.Start(ctx) }
func (rpm *RunProgressManager) Stop(ctx context.Context) error  { return rpm.BaseComponent.Stop(ctx) }

func (rpm *RunProgressManager) Set(runID int64, current, total int64, msg string) {
	if total < 0 {
		total = 0
	}
	if current < 0 {
		current = 0
	}
	if total > 0 && current > total {
		current = total
	}
	percent := 0
	if total > 0 {
		percent = int((current * 100) / total)
	}
	rpm.mu.Lock()
	rpm.data[runID] = &RunProgress{RunID: runID, Current: current, Total: total, Percent: percent, Message: msg, Updated: time.Now()}
	rpm.mu.Unlock()
}

func (rpm *RunProgressManager) Get(runID int64) *RunProgress {
	rpm.mu.RLock()
	defer rpm.mu.RUnlock()
	return rpm.data[runID]
}

// Clear removes progress for a finished run (should be called after terminal state)
func (rpm *RunProgressManager) Clear(runID int64) {
	rpm.mu.Lock()
	delete(rpm.data, runID)
	rpm.mu.Unlock()
}

// AttemptCleanup removes stale progress objects older than ttl.
func (rpm *RunProgressManager) AttemptCleanup(ctx context.Context, ttl time.Duration) {
	if ttl <= 0 {
		ttl = 10 * time.Minute
	}
	select {
	case <-ctx.Done():
		return
	default:
	}
	now := time.Now()
	rpm.mu.Lock()
	for id, p := range rpm.data {
		if now.Sub(p.Updated) > ttl {
			delete(rpm.data, id)
		}
	}
	rpm.mu.Unlock()
}
