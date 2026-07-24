package service

import (
	"context"
	"testing"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// stubDao implements TaskDao for TaskService tests
type stubDao struct{ tasks map[int64]*model.Task }

func (s *stubDao) Create(ctx context.Context, t *model.Task) error        { s.tasks[t.ID] = t; return nil }
func (s *stubDao) Get(ctx context.Context, id int64) (*model.Task, error) { return s.tasks[id], nil }
func (s *stubDao) ListEnabled(ctx context.Context) ([]*model.Task, error) {
	var out []*model.Task
	for _, t := range s.tasks {
		if t.Status == bizConsts.ENABLED {
			out = append(out, t)
		}
	}
	return out, nil
}
func (s *stubDao) UpdateCronAndMeta(ctx context.Context, t *model.Task) error {
	s.tasks[t.ID] = t
	t.Version++
	return nil
}
func (s *stubDao) UpdateStatus(ctx context.Context, id int64, status bizConsts.TaskStatus) error {
	if t := s.tasks[id]; t != nil {
		t.Status = status
		t.Version++
	}
	return nil
}
func (s *stubDao) SoftDelete(ctx context.Context, id int64) error {
	if t := s.tasks[id]; t != nil {
		t.Deleted = 1
	}
	return nil
}

// 以下方法为接口补全（stubDao 仅供 TaskService 缓存测试使用，简单实现即可）。
func (s *stubDao) ExistsByName(ctx context.Context, name string) bool {
	for _, t := range s.tasks {
		if t.Name == name && t.Deleted == 0 {
			return true
		}
	}
	return false
}
func (s *stubDao) ReactivateByName(ctx context.Context, name string, t *model.Task) (int64, bool, error) {
	for id, existing := range s.tasks {
		if existing.Name == name && existing.Deleted == 1 {
			existing.Deleted = 0
			return id, true, nil
		}
	}
	return 0, false, nil
}
func (s *stubDao) ListFiltered(ctx context.Context, f *model.TaskListFilters, limit, offset int) ([]*model.Task, error) {
	var out []*model.Task
	for _, t := range s.tasks {
		if t.Deleted == 0 {
			out = append(out, t)
		}
	}
	return out, nil
}
func (s *stubDao) CountFiltered(ctx context.Context, f *model.TaskListFilters) (int64, error) {
	rows, _ := s.ListFiltered(ctx, f, 0, 0)
	return int64(len(rows)), nil
}

func TestTaskServiceCacheLifecycle(t *testing.T) {
	da := &stubDao{tasks: map[int64]*model.Task{1: {ID: 1, Name: "t1", CronExpr: "* * * * * *", Status: bizConsts.ENABLED, Version: 1}, 2: {ID: 2, Name: "t2", CronExpr: "* * * * * *", Status: bizConsts.DISABLED, Version: 1}}}
	ts := NewTaskService()
	ts.TaskDao = da
	if err := ts.Start(context.Background()); err != nil {
		t.Fatalf("start failed: %v", err)
	}
	list, _ := ts.ListEnabled(context.Background())
	if len(list) != 1 {
		t.Fatalf("expected 1 enabled task, got %d", len(list))
	}
	// enable second
	if err := ts.UpdateStatus(context.Background(), 2, bizConsts.ENABLED); err != nil {
		t.Fatalf("update status failed: %v", err)
	}
	list, _ = ts.ListEnabled(context.Background())
	if len(list) != 2 {
		t.Fatalf("expected 2 enabled tasks, got %d", len(list))
	}
	// disable first
	if err := ts.UpdateStatus(context.Background(), 1, bizConsts.DISABLED); err != nil {
		t.Fatalf("update status failed: %v", err)
	}
	list, _ = ts.ListEnabled(context.Background())
	if len(list) != 1 {
		t.Fatalf("expected 1 enabled task after disable, got %d", len(list))
	}
}
