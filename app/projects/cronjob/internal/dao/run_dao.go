package dao

import (
	"context"
	"fmt"
	"strings"

	"gorm.io/gorm"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type RunDao interface {
	// Embed component so registry builders can return a RunDao where core.Component is required
	core.Component
	CreateScheduled(ctx context.Context, run *model.TaskRun) error
	TransitionToRunning(ctx context.Context, runID int64) (bool, error)
	MarkSuccess(ctx context.Context, runID int64, code int, body string) error
	MarkFailed(ctx context.Context, runID int64, errMsg string) error
	MarkCanceled(ctx context.Context, runID int64) error
	MarkSkipped(ctx context.Context, runID int64) error
	Get(ctx context.Context, id int64) (*model.TaskRun, error)
	ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error)
}

type runDaoImpl struct {
	db *gorm.DB
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	dsName   string            // 数据源名称
}

func NewRunDao(dsName string) RunDao {
	return &runDaoImpl{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_RUN, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

func (d *runDaoImpl) Start(ctx context.Context) error {
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return fmt.Errorf("get gorm db %s failed: %w", d.dsName, err)
	}
	d.db = db
	return nil
}

func (d *runDaoImpl) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (r *runDaoImpl) CreateScheduled(ctx context.Context, run *model.TaskRun) error {
	if run.Status == "" {
		run.Status = model.RunStatusScheduled
	}
	if run.Attempt == 0 {
		run.Attempt = 1
	}
	if strings.TrimSpace(run.RequestHeaders) == "" { // JSON column requires valid document
		run.RequestHeaders = bizConsts.DEFAULT_JSON_STR
	}
	return r.db.WithContext(ctx).Create(run).Error
}

func (r *runDaoImpl) TransitionToRunning(ctx context.Context, runID int64) (bool, error) {
	res := r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, model.RunStatusScheduled).Updates(map[string]any{"status": model.RunStatusRunning, "start_time": gorm.Expr("NOW()")})
	return res.RowsAffected == 1 && res.Error == nil, res.Error
}

func (r *runDaoImpl) MarkSuccess(ctx context.Context, runID int64, code int, body string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=?", runID).Updates(map[string]any{"status": model.RunStatusSuccess, "response_code": code, "response_body": body, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkFailed(ctx context.Context, runID int64, errMsg string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []model.RunStatus{model.RunStatusRunning, model.RunStatusScheduled}).Updates(map[string]any{"status": model.RunStatusFailed, "error_message": errMsg, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkCanceled(ctx context.Context, runID int64) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []model.RunStatus{model.RunStatusScheduled, model.RunStatusRunning}).Updates(map[string]any{"status": model.RunStatusCanceled, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkSkipped(ctx context.Context, runID int64) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, model.RunStatusScheduled).Updates(map[string]any{"status": model.RunStatusSkipped, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) Get(ctx context.Context, id int64) (*model.TaskRun, error) {
	var run model.TaskRun
	if err := r.db.WithContext(ctx).Where("id=?", id).First(&run).Error; err != nil {
		return nil, err
	}
	return &run, nil
}

func (r *runDaoImpl) ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error) {
	var list []*model.TaskRun
	q := r.db.WithContext(ctx).Where("task_id=?", taskID).Order("id DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}
