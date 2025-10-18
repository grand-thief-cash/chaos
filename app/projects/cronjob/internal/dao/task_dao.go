package dao

import (
	"context"
	"fmt"
	"strings"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type TaskDao interface {
	Create(ctx context.Context, t *model.Task) error
	Get(ctx context.Context, id int64) (*model.Task, error)
	ListEnabled(ctx context.Context) ([]*model.Task, error)
	UpdateCronAndMeta(ctx context.Context, t *model.Task) error
	UpdateStatus(ctx context.Context, id int64, status bizConsts.TaskStatus) error
	SoftDelete(ctx context.Context, id int64) error
}

type TaskDaoImpl struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string // 数据源名称（示例用 "main"）
}

// NewTaskDao now only needs dsName; mysql_gorm injected via tag.
func NewTaskDao(dsName string) *TaskDaoImpl {
	return &TaskDaoImpl{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_TASK, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

// This start func is a implementation of BaseComponent's start method.
func (d *TaskDaoImpl) Start(ctx context.Context) error {
	// 标记 active（也可以先做依赖检查，再 SetActive）
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	// 到这里 mysql_gorm 已经被框架保证先启动（因为 Dependencies 中声明）
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return fmt.Errorf("get gorm db %s failed: %w", d.dsName, err)
	}
	d.db = db
	return nil
}

func (d *TaskDaoImpl) Stop(ctx context.Context) error {
	// 标记 inactive
	return d.BaseComponent.Stop(ctx)
}

func (d *TaskDaoImpl) Create(ctx context.Context, t *model.Task) error {
	if t.Version == 0 {
		t.Version = 1
	}
	if strings.TrimSpace(t.HeadersJSON) == "" {
		t.HeadersJSON = bizConsts.DEFAULT_JSON_STR
	}
	if strings.TrimSpace(t.RetryPolicyJSON) == "" {
		t.RetryPolicyJSON = bizConsts.DEFAULT_JSON_STR
	}
	return d.db.WithContext(ctx).Create(t).Error
}

func (d *TaskDaoImpl) Get(ctx context.Context, id int64) (*model.Task, error) {
	var t model.Task
	if err := d.db.WithContext(ctx).Where("id=? AND deleted=0", id).First(&t).Error; err != nil {
		return nil, err
	}
	return &t, nil
}

func (d *TaskDaoImpl) ListEnabled(ctx context.Context) ([]*model.Task, error) {
	var list []*model.Task
	if err := d.db.WithContext(ctx).Where("status=? AND deleted=0", "ENABLED").Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

func (d *TaskDaoImpl) UpdateCronAndMeta(ctx context.Context, t *model.Task) error {
	if strings.TrimSpace(t.HeadersJSON) == "" {
		t.HeadersJSON = bizConsts.DEFAULT_JSON_STR
	}
	if strings.TrimSpace(t.RetryPolicyJSON) == "" {
		t.RetryPolicyJSON = bizConsts.DEFAULT_JSON_STR
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
	res := d.db.WithContext(ctx).Model(&model.Task{}).
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

func (d *TaskDaoImpl) UpdateStatus(ctx context.Context, id int64, status bizConsts.TaskStatus) error {
	res := d.db.WithContext(ctx).Model(&model.Task{}).Where("id=? AND deleted=0", id).Updates(map[string]any{"status": status, "version": gorm.Expr("version+1")})
	return res.Error
}

func (d *TaskDaoImpl) SoftDelete(ctx context.Context, id int64) error {
	return d.db.WithContext(ctx).Model(&model.Task{}).Where("id=?", id).Update("deleted", 1).Error
}
