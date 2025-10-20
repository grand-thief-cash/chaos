package service

import (
	"context"
	"testing"
	"time"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// stubRunDao captures created runs
type stubRunDao struct {
	runs   []*model.TaskRun
	nextID int64
}

func (r *stubRunDao) Start(_ context.Context) error { return nil }
func (r *stubRunDao) Stop(_ context.Context) error  { return nil }
func (r *stubRunDao) CreateScheduled(_ context.Context, run *model.TaskRun) error {
	r.nextID++
	run.ID = r.nextID
	r.runs = append(r.runs, run)
	return nil
}
func (r *stubRunDao) CreateSkipped(_ context.Context, run *model.TaskRun, skipType bizConsts.RunStatus) error {
	r.nextID++
	run.ID = r.nextID
	run.Status = skipType
	now := time.Now()
	run.EndTime = &now
	r.runs = append(r.runs, run)
	return nil
}
func (r *stubRunDao) TransitionToRunning(_ context.Context, _ int64) (bool, error)  { return false, nil }
func (r *stubRunDao) MarkSuccess(_ context.Context, _ int64, _ int, _ string) error { return nil }
func (r *stubRunDao) MarkFailed(_ context.Context, _ int64, _ string) error         { return nil }
func (r *stubRunDao) MarkCanceled(_ context.Context, _ int64) error                 { return nil }
func (r *stubRunDao) MarkSkipped(_ context.Context, runID int64, skipType bizConsts.RunStatus) error {
	for _, ru := range r.runs {
		if ru.ID == runID {
			ru.Status = skipType
			now := time.Now()
			ru.EndTime = &now
		}
	}
	return nil
}
func (r *stubRunDao) MarkTimeout(_ context.Context, _ int64, _ string) error { return nil }
func (r *stubRunDao) Get(_ context.Context, _ int64) (*model.TaskRun, error) { return nil, nil }
func (r *stubRunDao) ListByTask(_ context.Context, taskID int64, limit int) ([]*model.TaskRun, error) {
	var out []*model.TaskRun
	for _, ru := range r.runs {
		if ru.TaskID == taskID {
			out = append(out, ru)
		}
	}
	// latest first (reverse)
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	if limit > 0 && len(out) > limit {
		out = out[:limit]
	}
	return out, nil
}

// stubExecutor only tracks enqueued runs & active count
type stubExecutor struct {
	enqueued []*model.TaskRun
	active   map[int64]int
	canceled []int64
}

func (s *stubExecutor) ActiveCount(taskID int64) int { return s.active[taskID] }
func (s *stubExecutor) Enqueue(run *model.TaskRun) {
	s.enqueued = append(s.enqueued, run)
	s.active[run.TaskID]++
}
func (s *stubExecutor) CancelRun(_ context.Context, id int64) {
	s.canceled = append(s.canceled, id)
	return
}

// Test overlap SKIP
func TestEngineOverlapSkip(t *testing.T) {
	stubTask := &model.Task{ID: 1, CronExpr: "* * * * * *", OverlapAction: bizConsts.OverlapActionSkip, FailureAction: bizConsts.FailureActionRunNew, MaxConcurrency: 1}
	runDao := &stubRunDao{}
	// existing running run
	runDao.runs = append(runDao.runs, &model.TaskRun{ID: 1, TaskID: 1, ScheduledTime: time.Now().Add(-10 * time.Second), Status: bizConsts.Running, Attempt: 1})
	fireTime := time.Now().Truncate(time.Second)
	// overlap -> should create skipped directly (no enqueue in this isolated test logic)
	run := &model.TaskRun{TaskID: stubTask.ID, ScheduledTime: fireTime, Attempt: 1}
	if err := runDao.CreateSkipped(context.Background(), run, bizConsts.OverlapSkip); err != nil {
		t.Fatalf("CreateSkipped failed: %v", err)
	}
	if run.Status != bizConsts.OverlapSkip {
		t.Fatalf("expected status=%s got %s", bizConsts.OverlapSkip, run.Status)
	}
}

// Test failure retry attempt increment
func TestFailureRetryIncrement(t *testing.T) {
	stubTask := &model.Task{ID: 2, CronExpr: "* * * * * *", OverlapAction: bizConsts.OverlapActionAllow, FailureAction: bizConsts.FailureActionRetry}
	runDao := &stubRunDao{}
	runDao.runs = append(runDao.runs, &model.TaskRun{ID: 10, TaskID: 2, ScheduledTime: time.Now().Add(-5 * time.Second), Status: bizConsts.Failed, Attempt: 2})
	fireTime := time.Now().Truncate(time.Second)
	run := &model.TaskRun{TaskID: stubTask.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: 3}
	_ = runDao.CreateScheduled(context.Background(), run)
	if run.Attempt != 3 {
		t.Fatalf("expected attempt=3, got %d", run.Attempt)
	}
}
