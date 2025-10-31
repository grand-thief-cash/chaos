package service

import (
	"context"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// RunService: thin layer delegating to RunDao (no caching) for consistency with TaskService.
type RunService struct {
	*core.BaseComponent
	RunDao dao.RunDao `infra:"dep:run_dao"`
}

func NewRunService() *RunService {
	return &RunService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_RUN)}
}

func (s *RunService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *RunService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

func (s *RunService) CreateScheduled(ctx context.Context, run *model.TaskRun) error {
	return s.RunDao.CreateScheduled(ctx, run)
}
func (s *RunService) TransitionToRunning(ctx context.Context, runID int64) (bool, error) {
	return s.RunDao.TransitionToRunning(ctx, runID)
}
func (s *RunService) MarkSuccess(ctx context.Context, runID int64, code int, body string) error {
	return s.RunDao.MarkSuccess(ctx, runID, code, body)
}
func (s *RunService) MarkFailed(ctx context.Context, runID int64, errMsg string) error {
	return s.RunDao.MarkFailed(ctx, runID, errMsg)
}
func (s *RunService) MarkCanceled(ctx context.Context, runID int64) error {
	return s.RunDao.MarkCanceled(ctx, runID)
}
func (s *RunService) MarkSkipped(ctx context.Context, runID int64, skipType bizConsts.RunStatus) error {
	return s.RunDao.MarkSkipped(ctx, runID, skipType)
}
func (s *RunService) MarkTimeout(ctx context.Context, runID int64, errMsg string) error {
	return s.RunDao.MarkTimeout(ctx, runID, errMsg)
}
func (s *RunService) Get(ctx context.Context, id int64) (*model.TaskRun, error) {
	return s.RunDao.Get(ctx, id)
}
func (s *RunService) ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error) {
	return s.RunDao.ListByTask(ctx, taskID, limit)
}
func (s *RunService) MarkCallbackPending(ctx context.Context, runID int64) error {
	return s.RunDao.MarkCallbackPending(ctx, runID)
}
func (s *RunService) MarkCallbackSuccess(ctx context.Context, runID int64, code int, body string) error {
	return s.RunDao.MarkCallbackSuccess(ctx, runID, code, body)
}
func (s *RunService) MarkFailedTimeout(ctx context.Context, runID int64, errMsg string) error {
	return s.RunDao.MarkFailedTimeout(ctx, runID, errMsg)
}
func (s *RunService) ListActive(ctx context.Context, limit int) ([]*model.TaskRun, error) {
	return s.RunDao.ListActive(ctx, limit)
}
func (s *RunService) MarkCallbackFailed(ctx context.Context, runID int64, errMsg string) error {
	return s.RunDao.MarkCallbackFailed(ctx, runID, errMsg)
}
func (s *RunService) ListCallbackPendingExpired(ctx context.Context, limit int) ([]*model.TaskRun, error) {
	return s.RunDao.ListCallbackPendingExpired(ctx, limit)
}
func (s *RunService) MarkCallbackPendingWithDeadline(ctx context.Context, runID int64, deadline time.Time) error {
	return s.RunDao.MarkCallbackPendingWithDeadline(ctx, runID, deadline)
}
func (s *RunService) ListByTaskFiltered(ctx context.Context, taskID int64, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int, timeField string) ([]*model.TaskRun, error) {
	return s.RunDao.ListByTaskFiltered(ctx, taskID, statuses, from, to, limit, offset, timeField)
}
func (s *RunService) ListActiveFiltered(ctx context.Context, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int, timeField string) ([]*model.TaskRun, error) {
	return s.RunDao.ListActiveFiltered(ctx, statuses, from, to, limit, offset, timeField)
}
func (s *RunService) CountStatusByTask(ctx context.Context, taskID int64) (map[bizConsts.RunStatus]int64, error) {
	return s.RunDao.CountStatusByTask(ctx, taskID)
}
