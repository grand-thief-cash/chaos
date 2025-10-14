package repository

import (
	"context"
	"database/sql"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type RunRepository interface {
	CreateScheduled(ctx context.Context, run *model.TaskRun) error
	TransitionToRunning(ctx context.Context, runID int64) (bool, error)
	MarkSuccess(ctx context.Context, runID int64, code int, body string) error
	MarkFailed(ctx context.Context, runID int64, errMsg string) error
	MarkCanceled(ctx context.Context, runID int64) error
	MarkSkipped(ctx context.Context, runID int64) error
	Get(ctx context.Context, id int64) (*model.TaskRun, error)
	ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error)
}

type runRepo struct{ db *sql.DB }

func NewRunRepository(db *sql.DB) RunRepository { return &runRepo{db: db} }

func (r *runRepo) CreateScheduled(ctx context.Context, run *model.TaskRun) error {
	res, err := r.db.ExecContext(ctx, `INSERT INTO task_runs(task_id,scheduled_time,status,attempt,callback_token) VALUES (?,?,?,?,?)`, run.TaskID, run.ScheduledTime, run.Status, run.Attempt, run.CallbackToken)
	if err != nil {
		return err
	}
	id, _ := res.LastInsertId()
	run.ID = id
	return nil
}

func (r *runRepo) TransitionToRunning(ctx context.Context, runID int64) (bool, error) {
	res, err := r.db.ExecContext(ctx, `UPDATE task_runs SET status='RUNNING', start_time=NOW() WHERE id=? AND status='SCHEDULED'`, runID)
	if err != nil {
		return false, err
	}
	affected, _ := res.RowsAffected()
	return affected == 1, nil
}

func (r *runRepo) MarkSuccess(ctx context.Context, runID int64, code int, body string) error {
	_, err := r.db.ExecContext(ctx, `UPDATE task_runs SET status='SUCCESS', response_code=?, response_body=?, end_time=NOW() WHERE id=?`, code, body, runID)
	return err
}

func (r *runRepo) MarkFailed(ctx context.Context, runID int64, errMsg string) error {
	_, err := r.db.ExecContext(ctx, `UPDATE task_runs SET status='FAILED', error_message=?, end_time=NOW() WHERE id=? AND status IN ('RUNNING','SCHEDULED')`, errMsg, runID)
	return err
}

func (r *runRepo) MarkCanceled(ctx context.Context, runID int64) error {
	_, err := r.db.ExecContext(ctx, `UPDATE task_runs SET status='CANCELED', end_time=NOW() WHERE id=? AND status IN ('SCHEDULED','RUNNING')`, runID)
	return err
}

func (r *runRepo) MarkSkipped(ctx context.Context, runID int64) error {
	_, err := r.db.ExecContext(ctx, `UPDATE task_runs SET status='SKIPPED', end_time=NOW() WHERE id=? AND status='SCHEDULED'`, runID)
	return err
}

func (r *runRepo) Get(ctx context.Context, id int64) (*model.TaskRun, error) {
	row := r.db.QueryRowContext(ctx, `SELECT id,task_id,scheduled_time,start_time,end_time,status,attempt,IFNULL(request_headers,''),IFNULL(request_body,''),response_code,IFNULL(response_body,''),IFNULL(error_message,''),next_retry_time,callback_token,callback_deadline,trace_id,created_at,updated_at FROM task_runs WHERE id=?`, id)
	run := &model.TaskRun{}
	var start, end, nextRetry, cbDeadline *time.Time
	var respCode *int
	if err := row.Scan(&run.ID, &run.TaskID, &run.ScheduledTime, &start, &end, &run.Status, &run.Attempt, &run.RequestHeaders, &run.RequestBody, &respCode, &run.ResponseBody, &run.ErrorMessage, &nextRetry, &run.CallbackToken, &cbDeadline, &run.TraceID, &run.CreatedAt, &run.UpdatedAt); err != nil {
		return nil, err
	}
	run.StartTime = start
	run.EndTime = end
	run.NextRetryTime = nextRetry
	run.CallbackDeadline = cbDeadline
	run.ResponseCode = respCode
	return run, nil
}

func (r *runRepo) ListByTask(ctx context.Context, taskID int64, limit int) ([]*model.TaskRun, error) {
	rows, err := r.db.QueryContext(ctx, `SELECT id,task_id,scheduled_time,start_time,end_time,status,attempt,IFNULL(request_headers,''),IFNULL(request_body,''),response_code,IFNULL(response_body,''),IFNULL(error_message,''),next_retry_time,callback_token,callback_deadline,trace_id,created_at,updated_at FROM task_runs WHERE task_id=? ORDER BY id DESC LIMIT ?`, taskID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []*model.TaskRun
	for rows.Next() {
		run := &model.TaskRun{}
		var start, end, nextRetry, cbDeadline *time.Time
		var respCode *int
		if err := rows.Scan(&run.ID, &run.TaskID, &run.ScheduledTime, &start, &end, &run.Status, &run.Attempt, &run.RequestHeaders, &run.RequestBody, &respCode, &run.ResponseBody, &run.ErrorMessage, &nextRetry, &run.CallbackToken, &cbDeadline, &run.TraceID, &run.CreatedAt, &run.UpdatedAt); err != nil {
			return nil, err
		}
		run.StartTime = start
		run.EndTime = end
		run.NextRetryTime = nextRetry
		run.CallbackDeadline = cbDeadline
		run.ResponseCode = respCode
		list = append(list, run)
	}
	return list, nil
}
