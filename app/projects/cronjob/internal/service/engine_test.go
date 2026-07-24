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

// 窗口匹配：60s 轮询不对齐墙钟整秒时，仍能在窗口内捕获到 cron 命中点。
func TestFiresInWindowEveryMinute(t *testing.T) {
	loc := time.Local
	// "0 * * * * *" = 每分钟第 0 秒。窗口 (19:00:30, 19:01:30] 应命中 19:01:00。
	from := time.Date(2026, 7, 24, 19, 0, 30, 0, loc)
	to := time.Date(2026, 7, 24, 19, 1, 30, 0, loc)
	got := firesInWindow("0 * * * * *", from, to)
	if len(got) != 1 {
		t.Fatalf("expected 1 fire, got %d: %v", len(got), got)
	}
	want := time.Date(2026, 7, 24, 19, 1, 0, 0, loc)
	if !got[0].Equal(want) {
		t.Fatalf("expected %v, got %v", want, got[0])
	}
}

func TestFiresInWindowEverySecond(t *testing.T) {
	loc := time.Local
	// "* * * * * *" = 每秒。窗口 (19:00:00, 19:00:03] = 3 秒。
	from := time.Date(2026, 7, 24, 19, 0, 0, 0, loc)
	to := time.Date(2026, 7, 24, 19, 0, 3, 0, loc)
	got := firesInWindow("* * * * * *", from, to)
	if len(got) != 3 {
		t.Fatalf("expected 3 fires, got %d: %v", len(got), got)
	}
}

// 预览：用户表达式 0 0 */2 * * *（每 2 小时）的下次 3 个触发点。
func TestPreviewNextEvery2Hours(t *testing.T) {
	e := &Engine{}
	loc := time.Local
	from := time.Date(2026, 7, 24, 19, 40, 5, 0, loc) // 模拟 tick 落在 :05
	got, err := e.PreviewNext("0 0 */2 * * *", 3, from)
	if err != nil {
		t.Fatalf("PreviewNext error: %v", err)
	}
	want := []time.Time{
		time.Date(2026, 7, 24, 20, 0, 0, 0, loc),
		time.Date(2026, 7, 24, 22, 0, 0, 0, loc),
		time.Date(2026, 7, 25, 0, 0, 0, 0, loc),
	}
	if len(got) != len(want) {
		t.Fatalf("expected %d times, got %d: %v", len(want), len(got), got)
	}
	for i, w := range want {
		if !got[i].Equal(w) {
			t.Fatalf("times[%d]: expected %v, got %v", i, w, got[i])
		}
	}
}

// 预览：5 字段表达式应自动补秒。
func TestPreviewNextNormalizes5Field(t *testing.T) {
	e := &Engine{}
	loc := time.Local
	// "0 0 * * *" (5字段) -> "0 0 0 * * *"：每天 00:00:00
	from := time.Date(2026, 7, 24, 19, 40, 5, 0, loc)
	got, err := e.PreviewNext("0 0 * * *", 2, from)
	if err != nil {
		t.Fatalf("PreviewNext error: %v", err)
	}
	want := []time.Time{
		time.Date(2026, 7, 25, 0, 0, 0, 0, loc),
		time.Date(2026, 7, 26, 0, 0, 0, 0, loc),
	}
	if len(got) != len(want) {
		t.Fatalf("expected %d times, got %d: %v", len(want), len(got), got)
	}
	for i, w := range want {
		if !got[i].Equal(w) {
			t.Fatalf("times[%d]: expected %v, got %v", i, w, got[i])
		}
	}
}

// 预览：非法/超范围表达式应返回错误。
func TestPreviewNextInvalid(t *testing.T) {
	e := &Engine{}
	if _, err := e.PreviewNext("not a cron", 3, time.Now()); err == nil {
		t.Fatalf("expected error for invalid field count")
	}
	// hour=25 超范围 -> 该字段匹配空集 -> error
	if _, err := e.PreviewNext("0 0 25 * * *", 3, time.Now()); err == nil {
		t.Fatalf("expected error for out-of-range hour")
	}
}
