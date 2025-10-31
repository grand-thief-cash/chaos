package dao

import (
	"context"
	"fmt"
	"strings"
	"time"

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
	CreateSkipped(ctx context.Context, run *model.TaskRun, skipType bizConsts.RunStatus) error // new helper to directly create a skipped run
	TransitionToRunning(ctx context.Context, runID int64) (bool, error)
	MarkSuccess(ctx context.Context, runID int64, code int, body string) error
	MarkFailed(ctx context.Context, runID int64, errMsg string) error
	MarkCanceled(ctx context.Context, runID int64) error
	MarkSkipped(ctx context.Context, runID int64, skipType bizConsts.RunStatus) error
	MarkTimeout(ctx context.Context, runID int64, errMsg string) error
	MarkCallbackPending(ctx context.Context, runID int64) error
	MarkCallbackSuccess(ctx context.Context, runID int64, code int, body string) error
	MarkFailedTimeout(ctx context.Context, runID int64, errMsg string) error
	MarkCallbackFailed(ctx context.Context, runID int64, errMsg string) error
	MarkCallbackPendingWithDeadline(ctx context.Context, runID int64, deadline time.Time) error
	Get(ctx context.Context, id int64) (*model.TaskRun, error)
	ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error)
	ListActive(ctx context.Context, limit int) ([]*model.TaskRun, error) // list currently active/pending runs
	ListCallbackPendingExpired(ctx context.Context, limit int) ([]*model.TaskRun, error)
	CountPerTask(ctx context.Context, limit int) (map[int64]int, error)
	DeleteOlderThan(ctx context.Context, taskID int64, deadline time.Time) (int64, error)
	DeleteKeepRecent(ctx context.Context, taskID int64, keep int) (int64, error)
	DeleteByIDs(ctx context.Context, ids []int64) (int64, error)
	ListIDsOffset(ctx context.Context, taskID int64, offset, limit int) ([]int64, error)
	ListByTaskFiltered(ctx context.Context, taskID int64, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int) ([]*model.TaskRun, error)
	ListActiveFiltered(ctx context.Context, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int) ([]*model.TaskRun, error)
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
		run.Status = bizConsts.Scheduled
	}
	if run.Attempt == 0 {
		run.Attempt = 1
	}
	if strings.TrimSpace(run.RequestHeaders) == "" { // JSON column requires valid document
		run.RequestHeaders = bizConsts.DEFAULT_JSON_STR
	}
	return r.db.WithContext(ctx).Create(run).Error
}

// CreateSkipped creates a run directly in a skipped terminal state (e.g. CONCURRENT_SKIP/OVERLAP_SKIP/FAILURE_SKIP)
// avoiding the two-step CreateScheduled + MarkSkipped update. end_time is set to NOW().
func (r *runDaoImpl) CreateSkipped(ctx context.Context, run *model.TaskRun, skipType bizConsts.RunStatus) error {
	if run.Attempt == 0 {
		run.Attempt = 1
	}
	if strings.TrimSpace(run.RequestHeaders) == "" {
		run.RequestHeaders = bizConsts.DEFAULT_JSON_STR
	}
	now := time.Now()
	run.Status = skipType
	run.EndTime = &now
	return r.db.WithContext(ctx).Create(run).Error
}

func (r *runDaoImpl) TransitionToRunning(ctx context.Context, runID int64) (bool, error) {
	res := r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, bizConsts.Scheduled).Updates(map[string]any{"status": bizConsts.Running, "start_time": gorm.Expr("NOW()")})
	return res.RowsAffected == 1 && res.Error == nil, res.Error
}

func (r *runDaoImpl) MarkSuccess(ctx context.Context, runID int64, code int, body string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=?", runID).Updates(map[string]any{"status": bizConsts.Success, "response_code": code, "response_body": body, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkFailed(ctx context.Context, runID int64, errMsg string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []bizConsts.RunStatus{bizConsts.Running, bizConsts.Scheduled}).Updates(map[string]any{"status": bizConsts.Failed, "error_message": errMsg, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkCanceled(ctx context.Context, runID int64) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []bizConsts.RunStatus{bizConsts.Scheduled, bizConsts.Running}).Updates(map[string]any{"status": bizConsts.Canceled, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkSkipped(ctx context.Context, runID int64, skipType bizConsts.RunStatus) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, bizConsts.Scheduled).Updates(map[string]any{"status": skipType, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkTimeout(ctx context.Context, runID int64, errMsg string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []bizConsts.RunStatus{bizConsts.Running, bizConsts.Scheduled}).Updates(map[string]any{"status": bizConsts.Timeout, "error_message": errMsg, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkCallbackPending(ctx context.Context, runID int64) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []bizConsts.RunStatus{bizConsts.Running, bizConsts.Scheduled}).Updates(map[string]any{"status": bizConsts.CallbackPending, "callback_deadline": time.Now().Add(5 * time.Minute)}).Error
}

func (r *runDaoImpl) MarkCallbackSuccess(ctx context.Context, runID int64, code int, body string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, bizConsts.CallbackPending).Updates(map[string]any{"status": bizConsts.CallbackSuccess, "response_code": code, "response_body": body, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkFailedTimeout(ctx context.Context, runID int64, errMsg string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, bizConsts.CallbackPending).Updates(map[string]any{"status": bizConsts.FailedTimeout, "error_message": errMsg, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkCallbackFailed(ctx context.Context, runID int64, errMsg string) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status=?", runID, bizConsts.CallbackPending).Updates(map[string]any{"status": bizConsts.CallbackFailed, "error_message": errMsg, "end_time": gorm.Expr("NOW()")}).Error
}

func (r *runDaoImpl) MarkCallbackPendingWithDeadline(ctx context.Context, runID int64, deadline time.Time) error {
	return r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("id=? AND status IN ?", runID, []bizConsts.RunStatus{bizConsts.Running, bizConsts.Scheduled}).Updates(map[string]any{"status": bizConsts.CallbackPending, "callback_deadline": deadline}).Error
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

func (r *runDaoImpl) ListActive(ctx context.Context, limit int) ([]*model.TaskRun, error) {
	var list []*model.TaskRun
	q := r.db.WithContext(ctx).Where("status IN ?", []bizConsts.RunStatus{bizConsts.Scheduled, bizConsts.Running, bizConsts.CallbackPending}).Order("id DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

func (r *runDaoImpl) ListCallbackPendingExpired(ctx context.Context, limit int) ([]*model.TaskRun, error) {
	var list []*model.TaskRun
	q := r.db.WithContext(ctx).Where("status=? AND callback_deadline IS NOT NULL AND callback_deadline < NOW()", bizConsts.CallbackPending).Order("id ASC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

func (r *runDaoImpl) CountPerTask(ctx context.Context, limit int) (map[int64]int, error) {
	rows, err := r.db.WithContext(ctx).Model(&model.TaskRun{}).Select("task_id, COUNT(*) as cnt").Group("task_id").Order("cnt DESC").Rows()
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	res := make(map[int64]int)
	for rows.Next() {
		var taskID int64
		var cnt int
		if err := rows.Scan(&taskID, &cnt); err != nil {
			return nil, err
		}
		res[taskID] = cnt
		if limit > 0 && len(res) >= limit {
			break
		}
	}
	return res, nil
}

func (r *runDaoImpl) DeleteOlderThan(ctx context.Context, taskID int64, deadline time.Time) (int64, error) {
	q := r.db.WithContext(ctx).Where("scheduled_time < ?", deadline)
	if taskID > 0 {
		q = q.Where("task_id=?", taskID)
	}
	res := q.Delete(&model.TaskRun{})
	return res.RowsAffected, res.Error
}

func (r *runDaoImpl) DeleteKeepRecent(ctx context.Context, taskID int64, keep int) (int64, error) {
	if keep <= 0 { // delete all for task or all tasks
		if taskID > 0 {
			res := r.db.WithContext(ctx).Where("task_id=?", taskID).Delete(&model.TaskRun{})
			return res.RowsAffected, res.Error
		}
		res := r.db.WithContext(ctx).Delete(&model.TaskRun{})
		return res.RowsAffected, res.Error
	}
	// delete older than top keep ids
	if taskID > 0 {
		var ids []int64
		if err := r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("task_id=?", taskID).Order("id DESC").Offset(keep).Pluck("id", &ids).Error; err != nil {
			return 0, err
		}
		if len(ids) == 0 {
			return 0, nil
		}
		res := r.db.WithContext(ctx).Where("id IN ?", ids).Delete(&model.TaskRun{})
		return res.RowsAffected, res.Error
	}
	// global scenario: iterate tasks
	counts, err := r.CountPerTask(ctx, 0)
	if err != nil {
		return 0, err
	}
	var total int64
	for tid := range counts {
		var ids []int64
		if err := r.db.WithContext(ctx).Model(&model.TaskRun{}).Where("task_id=?", tid).Order("id DESC").Offset(keep).Pluck("id", &ids).Error; err != nil {
			continue
		}
		if len(ids) == 0 {
			time.Sleep(500 * time.Millisecond)
			continue
		}
		res := r.db.WithContext(ctx).Where("id IN ?", ids).Delete(&model.TaskRun{})
		total += res.RowsAffected
		time.Sleep(500 * time.Millisecond) // throttle to reduce DB pressure
	}
	return total, nil
}

func (r *runDaoImpl) DeleteByIDs(ctx context.Context, ids []int64) (int64, error) {
	res := r.db.WithContext(ctx).Where("id IN ?", ids).Delete(&model.TaskRun{})
	return res.RowsAffected, res.Error
}

func (r *runDaoImpl) ListIDsOffset(ctx context.Context, taskID int64, offset, limit int) ([]int64, error) {
	var ids []int64
	q := r.db.WithContext(ctx).Model(&model.TaskRun{}).Order("id DESC").Offset(offset)
	if taskID > 0 {
		q = q.Where("task_id=?", taskID)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Pluck("id", &ids).Error; err != nil {
		return nil, err
	}
	return ids, nil
}

func (r *runDaoImpl) ListByTaskFiltered(ctx context.Context, taskID int64, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int) ([]*model.TaskRun, error) {
	var list []*model.TaskRun
	q := r.db.WithContext(ctx).Where("task_id=?", taskID)
	if len(statuses) > 0 {
		q = q.Where("status IN ?", statuses)
	}
	if from != nil {
		q = q.Where("scheduled_time >= ?", *from)
	}
	if to != nil {
		q = q.Where("scheduled_time <= ?", *to)
	}
	q = q.Order("id DESC")
	if offset > 0 {
		q = q.Offset(offset)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

func (r *runDaoImpl) ListActiveFiltered(ctx context.Context, statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int) ([]*model.TaskRun, error) {
	base := []bizConsts.RunStatus{bizConsts.Scheduled, bizConsts.Running, bizConsts.CallbackPending}
	if len(statuses) > 0 {
		base = statuses
	}
	var list []*model.TaskRun
	q := r.db.WithContext(ctx).Where("status IN ?", base)
	if from != nil {
		q = q.Where("scheduled_time >= ?", *from)
	}
	if to != nil {
		q = q.Where("scheduled_time <= ?", *to)
	}
	q = q.Order("id DESC")
	if offset > 0 {
		q = q.Offset(offset)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}
