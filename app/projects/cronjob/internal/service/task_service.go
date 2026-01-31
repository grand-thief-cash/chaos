package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// TaskService 负责 Task 的数据库访问 + 内存缓存（仅缓存 ENABLED 任务）
// 读操作（ListEnabled/GetEnabled）走内存；写操作成功后更新缓存。
// 并发安全：使用 RWMutex；ListEnabled 返回副本避免外部修改。
type TaskService struct {
	*core.BaseComponent
	TaskDao dao.TaskDao `infra:"dep:task_dao"`

	mu      sync.RWMutex
	enabled map[int64]*model.Task // 缓存所有 ENABLED && 未删除 的任务
}

func NewTaskService() *TaskService {
	return &TaskService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_TASK)}
}

func (s *TaskService) Start(ctx context.Context) error {
	if s.IsActive() {
		return nil
	}
	if err := s.BaseComponent.Start(ctx); err != nil {
		return err
	}
	list, err := s.TaskDao.ListEnabled(ctx)
	if err != nil {
		return err
	}
	s.mu.Lock()
	s.enabled = make(map[int64]*model.Task, len(list))
	for _, t := range list {
		s.enabled[t.ID] = t
	}
	s.mu.Unlock()
	logging.Info(ctx, fmt.Sprintf("task_service cache loaded count: %d", len(list)))
	return nil
}

func (s *TaskService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

// Create 创建任务并将 ENABLED 任务加入缓存
func (s *TaskService) Create(ctx context.Context, t *model.Task) error {
	if err := s.TaskDao.Create(ctx, t); err != nil {
		return err
	}
	if t.Status == bizConsts.ENABLED {
		s.mu.Lock()
		s.enabled[t.ID] = t
		s.mu.Unlock()
	}
	return nil
}

// Get 返回任务：若缓存中存在（仅 enabled）优先返回，否则查 DB。
func (s *TaskService) Get(ctx context.Context, id int64) (*model.Task, error) {
	s.mu.RLock()
	t, ok := s.enabled[id]
	s.mu.RUnlock()
	if ok {
		return t, nil
	}
	return s.TaskDao.Get(ctx, id)
}

// ListEnabled 从缓存返回所有 ENABLED 任务的副本
func (s *TaskService) ListEnabled(ctx context.Context) ([]*model.Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*model.Task, 0, len(s.enabled))
	for _, t := range s.enabled {
		out = append(out, t)
	}
	return out, nil
}

// UpdateCronAndMeta 更新任务元数据（乐观锁），若任务仍处于 ENABLED 则更新缓存副本。
func (s *TaskService) UpdateCronAndMeta(ctx context.Context, t *model.Task) error {
	if err := s.TaskDao.UpdateCronAndMeta(ctx, t); err != nil {
		return err
	}
	if t.Status == bizConsts.ENABLED {
		s.mu.Lock()
		s.enabled[t.ID] = t
		s.mu.Unlock()
	}
	return nil
}

// UpdateStatus 更新任务状态并同步缓存。
func (s *TaskService) UpdateStatus(ctx context.Context, id int64, status bizConsts.TaskStatus) error {
	if err := s.TaskDao.UpdateStatus(ctx, id, status); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if status == bizConsts.ENABLED {
		// 重新读取最新任务（包含版本等字段）
		if t, err := s.TaskDao.Get(ctx, id); err == nil && t.Status == bizConsts.ENABLED {
			s.enabled[id] = t
		}
	} else {
		delete(s.enabled, id)
	}
	return nil
}

// SoftDelete 软删除并移出缓存。
func (s *TaskService) SoftDelete(ctx context.Context, id int64) error {
	if err := s.TaskDao.SoftDelete(ctx, id); err != nil {
		return err
	}
	s.mu.Lock()
	delete(s.enabled, id)
	s.mu.Unlock()
	return nil
}

// Refresh 强制全量重载（可用于运维手动调用）
func (s *TaskService) Refresh(ctx context.Context) error {
	list, err := s.TaskDao.ListEnabled(ctx)
	if err != nil {
		return err
	}
	s.mu.Lock()
	s.enabled = make(map[int64]*model.Task, len(list))
	for _, t := range list {
		s.enabled[t.ID] = t
	}
	s.mu.Unlock()
	return nil
}

func (s *TaskService) ListFiltered(ctx context.Context, f *model.TaskListFilters, limit, offset int) ([]*model.Task, error) {
	return s.TaskDao.ListFiltered(ctx, f, limit, offset)
}

func (s *TaskService) CountFiltered(ctx context.Context, f *model.TaskListFilters) (int64, error) {
	return s.TaskDao.CountFiltered(ctx, f)
}

// CreateTaskRun 从 Task 创建 TaskRun，统一初始化逻辑
func (s *TaskService) CreateTaskRun(task *model.Task, scheduledTime time.Time, attempt int) *model.TaskRun {
	return &model.TaskRun{
		TaskID:             task.ID,
		ScheduledTime:      scheduledTime,
		Status:             bizConsts.Scheduled,
		Attempt:            attempt,
		TargetService:      task.TargetService,
		TargetPath:         task.TargetPath,
		Method:             task.HTTPMethod,
		ExecType:           task.ExecType,
		CallbackTimeoutSec: task.CallbackTimeoutSec,
		RequestHeaders:     task.HeadersJSON,
		RequestBody:        task.BodyTemplate,
	}
}
