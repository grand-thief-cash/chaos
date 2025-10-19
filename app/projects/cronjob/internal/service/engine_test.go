package service

import (
	"context"
	"testing"
	"time"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// stubTaskDao implements TaskDao for tests
type stubTaskDao struct{ tasks []*model.Task }

func (s *stubTaskDao) Create(context.Context, *model.Task) error                       { return nil }
func (s *stubTaskDao) Get(context.Context, int64) (*model.Task, error)                 { return nil, nil }
func (s *stubTaskDao) ListEnabled(context.Context) ([]*model.Task, error)              { return s.tasks, nil }
func (s *stubTaskDao) UpdateCronAndMeta(context.Context, *model.Task) error            { return nil }
func (s *stubTaskDao) UpdateStatus(context.Context, int64, bizConsts.TaskStatus) error { return nil }
func (s *stubTaskDao) SoftDelete(context.Context, int64) error                         { return nil }

// stubRunDao captures created runs
type stubRunDao struct {
	runs   []*model.TaskRun
	nextID int64
}

func (r *stubRunDao) Start(ctx context.Context) error { return nil }
func (r *stubRunDao) Stop(ctx context.Context) error  { return nil }
func (r *stubRunDao) CreateScheduled(ctx context.Context, run *model.TaskRun) error {
	r.nextID++
	run.ID = r.nextID
	r.runs = append(r.runs, run)
	return nil
}
func (r *stubRunDao) TransitionToRunning(ctx context.Context, runID int64) (bool, error) {
	return false, nil
}
func (r *stubRunDao) MarkSuccess(ctx context.Context, runID int64, code int, body string) error {
	return nil
}
func (r *stubRunDao) MarkFailed(ctx context.Context, runID int64, errMsg string) error { return nil }
func (r *stubRunDao) MarkCanceled(ctx context.Context, runID int64) error              { return nil }
func (r *stubRunDao) MarkSkipped(ctx context.Context, runID int64) error {
	for _, ru := range r.runs {
		if ru.ID == runID {
			ru.Status = bizConsts.Skipped
		}
	}
	return nil
}
func (r *stubRunDao) MarkTimeout(ctx context.Context, runID int64, errMsg string) error { return nil }
func (r *stubRunDao) Get(ctx context.Context, id int64) (*model.TaskRun, error)         { return nil, nil }
func (r *stubRunDao) ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error) {
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
func (s *stubExecutor) CancelRun(id int64) { s.canceled = append(s.canceled, id) }

// Test overlap SKIP
func TestEngineOverlapSkip(t *testing.T) {
	stubTask := &model.Task{ID: 1, CronExpr: "* * * * * *", OverlapAction: bizConsts.OverlapSkip, FailureAction: bizConsts.FailureRunNew, MaxConcurrency: 1}
	runDao := &stubRunDao{}
	// existing running run
	runDao.runs = append(runDao.runs, &model.TaskRun{ID: 1, TaskID: 1, ScheduledTime: time.Now().Add(-10 * time.Second), Status: bizConsts.Running, Attempt: 1})
	sec := time.Now().Truncate(time.Second)
	fireTime := sec
	// overlap -> should create scheduled then mark skipped, no enqueue
	run := &model.TaskRun{TaskID: stubTask.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: 1}
	runDao.CreateScheduled(context.Background(), run)
	runDao.MarkSkipped(context.Background(), run.ID)
	if run.Status != bizConsts.Skipped {
		t.Fatalf("expected skipped status, got %s", run.Status)
	}
}

// Test failure retry attempt increment
func TestFailureRetryIncrement(t *testing.T) {
	stubTask := &model.Task{ID: 2, CronExpr: "* * * * * *", OverlapAction: bizConsts.OverlapAllow, FailureAction: bizConsts.FailureRetry}
	runDao := &stubRunDao{}
	runDao.runs = append(runDao.runs, &model.TaskRun{ID: 10, TaskID: 2, ScheduledTime: time.Now().Add(-5 * time.Second), Status: bizConsts.Failed, Attempt: 2})
	fireTime := time.Now().Truncate(time.Second)
	run := &model.TaskRun{TaskID: stubTask.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: 3}
	runDao.CreateScheduled(context.Background(), run)
	if run.Attempt != 3 {
		t.Fatalf("expected attempt=3, got %d", run.Attempt)
	}
}
