package repository

import (
	"context"
	"database/sql"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type TaskRepository interface {
	Create(ctx context.Context, t *model.Task) error
	Get(ctx context.Context, id int64) (*model.Task, error)
	ListEnabled(ctx context.Context) ([]*model.Task, error)
	UpdateCronAndMeta(ctx context.Context, t *model.Task) error
	UpdateStatus(ctx context.Context, id int64, status string) error
	SoftDelete(ctx context.Context, id int64) error
}

type taskRepo struct{ db *sql.DB }

func NewTaskRepository(db *sql.DB) TaskRepository { return &taskRepo{db: db} }

func (r *taskRepo) Create(ctx context.Context, t *model.Task) error {
	res, err := r.db.ExecContext(ctx, `INSERT INTO tasks(name,description,cron_expr,timezone,exec_type,http_method,target_url,headers_json,body_template,timeout_seconds,retry_policy_json,max_concurrency,concurrency_policy,misfire_policy,catchup_limit,callback_method,callback_timeout_sec,status,version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)`,
		t.Name, t.Description, t.CronExpr, t.Timezone, t.ExecType, t.HTTPMethod, t.TargetURL, t.HeadersJSON, t.BodyTemplate, t.TimeoutSeconds, t.RetryPolicyJSON, t.MaxConcurrency, t.ConcurrencyPolicy, t.MisfirePolicy, t.CatchupLimit, t.CallbackMethod, t.CallbackTimeoutSec, t.Status)
	if err != nil {
		return err
	}
	id, _ := res.LastInsertId()
	t.ID = id
	return nil
}

func (r *taskRepo) Get(ctx context.Context, id int64) (*model.Task, error) {
	row := r.db.QueryRowContext(ctx, `SELECT id,name,description,cron_expr,timezone,exec_type,http_method,target_url,IFNULL(headers_json,''),IFNULL(body_template,''),timeout_seconds,IFNULL(retry_policy_json,''),max_concurrency,concurrency_policy,misfire_policy,catchup_limit,callback_method,callback_timeout_sec,status,version,created_at,updated_at FROM tasks WHERE id=? AND deleted=0`, id)
	t := &model.Task{}
	if err := row.Scan(&t.ID, &t.Name, &t.Description, &t.CronExpr, &t.Timezone, &t.ExecType, &t.HTTPMethod, &t.TargetURL, &t.HeadersJSON, &t.BodyTemplate, &t.TimeoutSeconds, &t.RetryPolicyJSON, &t.MaxConcurrency, &t.ConcurrencyPolicy, &t.MisfirePolicy, &t.CatchupLimit, &t.CallbackMethod, &t.CallbackTimeoutSec, &t.Status, &t.Version, &t.CreatedAt, &t.UpdatedAt); err != nil {
		return nil, err
	}
	return t, nil
}

func (r *taskRepo) ListEnabled(ctx context.Context) ([]*model.Task, error) {
	rows, err := r.db.QueryContext(ctx, `SELECT id,name,description,cron_expr,timezone,exec_type,http_method,target_url,IFNULL(headers_json,''),IFNULL(body_template,''),timeout_seconds,IFNULL(retry_policy_json,''),max_concurrency,concurrency_policy,misfire_policy,catchup_limit,callback_method,callback_timeout_sec,status,version,created_at,updated_at FROM tasks WHERE status='ENABLED' AND deleted=0`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []*model.Task
	for rows.Next() {
		t := &model.Task{}
		if err := rows.Scan(&t.ID, &t.Name, &t.Description, &t.CronExpr, &t.Timezone, &t.ExecType, &t.HTTPMethod, &t.TargetURL, &t.HeadersJSON, &t.BodyTemplate, &t.TimeoutSeconds, &t.RetryPolicyJSON, &t.MaxConcurrency, &t.ConcurrencyPolicy, &t.MisfirePolicy, &t.CatchupLimit, &t.CallbackMethod, &t.CallbackTimeoutSec, &t.Status, &t.Version, &t.CreatedAt, &t.UpdatedAt); err != nil {
			return nil, err
		}
		list = append(list, t)
	}
	return list, nil
}

func (r *taskRepo) UpdateCronAndMeta(ctx context.Context, t *model.Task) error {
	_, err := r.db.ExecContext(ctx, `UPDATE tasks SET description=?,cron_expr=?,timezone=?,exec_type=?,http_method=?,target_url=?,headers_json=?,body_template=?,timeout_seconds=?,retry_policy_json=?,max_concurrency=?,concurrency_policy=?,misfire_policy=?,catchup_limit=?,callback_method=?,callback_timeout_sec=?,version=version+1 WHERE id=? AND deleted=0`,
		t.Description, t.CronExpr, t.Timezone, t.ExecType, t.HTTPMethod, t.TargetURL, t.HeadersJSON, t.BodyTemplate, t.TimeoutSeconds, t.RetryPolicyJSON, t.MaxConcurrency, t.ConcurrencyPolicy, t.MisfirePolicy, t.CatchupLimit, t.CallbackMethod, t.CallbackTimeoutSec, t.ID)
	return err
}

func (r *taskRepo) UpdateStatus(ctx context.Context, id int64, status string) error {
	_, err := r.db.ExecContext(ctx, `UPDATE tasks SET status=?,version=version+1 WHERE id=? AND deleted=0`, status, id)
	return err
}

func (r *taskRepo) SoftDelete(ctx context.Context, id int64) error {
	_, err := r.db.ExecContext(ctx, `UPDATE tasks SET deleted=1 WHERE id=?`, id)
	return err
}
