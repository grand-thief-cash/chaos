package dao

import (
	"context"
	"strings"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type TaskDao interface {
	Create(ctx context.Context, t *model.Task) error
	Get(ctx context.Context, id int64) (*model.Task, error)
	ListEnabled(ctx context.Context) ([]*model.Task, error)
	UpdateCronAndMeta(ctx context.Context, t *model.Task) error
	UpdateStatus(ctx context.Context, id int64, status string) error
	SoftDelete(ctx context.Context, id int64) error
}

type taskDaoImpl struct{ db *gorm.DB }

func NewTaskDao(db *gorm.DB) TaskDao { return &taskDaoImpl{db: db} }

func (r *taskDaoImpl) Create(ctx context.Context, t *model.Task) error {
	if t.Version == 0 {
		t.Version = 1
	}
	if strings.TrimSpace(t.HeadersJSON) == "" {
		t.HeadersJSON = "{}"
	}
	if strings.TrimSpace(t.RetryPolicyJSON) == "" {
		t.RetryPolicyJSON = "{}"
	}
	return r.db.WithContext(ctx).Create(t).Error
}

func (r *taskDaoImpl) Get(ctx context.Context, id int64) (*model.Task, error) {
	var t model.Task
	if err := r.db.WithContext(ctx).Where("id=? AND deleted=0", id).First(&t).Error; err != nil {
		return nil, err
	}
	return &t, nil
}

func (r *taskDaoImpl) ListEnabled(ctx context.Context) ([]*model.Task, error) {
	var list []*model.Task
	if err := r.db.WithContext(ctx).Where("status=? AND deleted=0", "ENABLED").Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

func (r *taskDaoImpl) UpdateCronAndMeta(ctx context.Context, t *model.Task) error {
	if strings.TrimSpace(t.HeadersJSON) == "" {
		t.HeadersJSON = "{}"
	}
	if strings.TrimSpace(t.RetryPolicyJSON) == "" {
		t.RetryPolicyJSON = "{}"
	}
	updates := map[string]interface{}{
		"description":          t.Description,
		"cron_expr":            t.CronExpr,
		"timezone":             t.Timezone,
		"exec_type":            t.ExecType,
		"http_method":          t.HTTPMethod,
		"target_url":           t.TargetURL,
		"headers_json":         t.HeadersJSON,
		"body_template":        t.BodyTemplate,
		"timeout_seconds":      t.TimeoutSeconds,
		"retry_policy_json":    t.RetryPolicyJSON,
		"max_concurrency":      t.MaxConcurrency,
		"concurrency_policy":   t.ConcurrencyPolicy,
		"misfire_policy":       t.MisfirePolicy,
		"catchup_limit":        t.CatchupLimit,
		"callback_method":      t.CallbackMethod,
		"callback_timeout_sec": t.CallbackTimeoutSec,
		"version":              gorm.Expr("version + 1"),
	}
	// optimistic lock with version
	res := r.db.WithContext(ctx).Model(&model.Task{}).
		Where("id=? AND version=? AND deleted=0", t.ID, t.Version).
		Clauses(clause.Locking{Strength: "UPDATE"}).
		Updates(updates)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	// bump local struct version to reflect DB state
	t.Version++
	return nil
}

func (r *taskDaoImpl) UpdateStatus(ctx context.Context, id int64, status string) error {
	res := r.db.WithContext(ctx).Model(&model.Task{}).Where("id=? AND deleted=0", id).Updates(map[string]any{"status": status, "version": gorm.Expr("version+1")})
	return res.Error
}

func (r *taskDaoImpl) SoftDelete(ctx context.Context, id int64) error {
	return r.db.WithContext(ctx).Model(&model.Task{}).Where("id=?", id).Update("deleted", 1).Error
}
