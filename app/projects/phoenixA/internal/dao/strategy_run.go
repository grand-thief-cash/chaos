package dao

import (
	"context"
	"fmt"
	"strings"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type StrategyRunDao struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewStrategyRunDao(dsName string) *StrategyRunDao {
	return &StrategyRunDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_STRATEGY_RUN),
		dsName:        dsName,
	}
}

func (d *StrategyRunDao) Start(ctx context.Context) error {
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

func (d *StrategyRunDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *StrategyRunDao) UpsertSummary(ctx context.Context, summary *model.StrategyRunSummary) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "run_id"}},
		DoUpdates: clause.AssignmentColumns([]string{"parent_run_id", "task_code", "mode", "strategy_code", "symbol", "timeframe", "start_date", "end_date", "start_cash", "end_value", "pnl", "pnl_pct", "max_drawdown", "sharpe", "trade_count", "win_count", "loss_count", "win_rate", "bars_processed", "status", "stop_reason", "error_message", "duration_ms", "updated_at"}),
	}).Create(summary).Error
}

func (d *StrategyRunDao) UpsertArtifacts(ctx context.Context, artifacts []*model.StrategyRunArtifact) error {
	if len(artifacts) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "run_id"}, {Name: "artifact_type"}},
		DoUpdates: clause.AssignmentColumns([]string{"payload_json", "payload_version", "updated_at"}),
	}).Create(&artifacts).Error
}

func (d *StrategyRunDao) GetSummary(ctx context.Context, runID string) (*model.StrategyRunSummary, error) {
	var out model.StrategyRunSummary
	if err := d.db.WithContext(ctx).Where("run_id = ?", strings.TrimSpace(runID)).First(&out).Error; err != nil {
		return nil, err
	}
	return &out, nil
}

func (d *StrategyRunDao) ListSummaries(ctx context.Context, filter *model.StrategyRunSummaryFilters, limit, offset int) ([]*model.StrategyRunSummary, error) {
	q := d.db.WithContext(ctx).Model(&model.StrategyRunSummary{}).Order("created_at DESC")
	if filter != nil {
		if strings.TrimSpace(filter.RunID) != "" {
			q = q.Where("run_id = ?", strings.TrimSpace(filter.RunID))
		}
		if strings.TrimSpace(filter.ParentRunID) != "" {
			q = q.Where("parent_run_id = ?", strings.TrimSpace(filter.ParentRunID))
		}
		if strings.TrimSpace(filter.StrategyCode) != "" {
			q = q.Where("strategy_code = ?", strings.TrimSpace(filter.StrategyCode))
		}
		if strings.TrimSpace(filter.Symbol) != "" {
			q = q.Where("symbol = ?", strings.TrimSpace(filter.Symbol))
		}
		if strings.TrimSpace(filter.Status) != "" {
			q = q.Where("status = ?", strings.TrimSpace(filter.Status))
		}
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	var out []*model.StrategyRunSummary
	if err := q.Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}

func (d *StrategyRunDao) ListArtifactsByRunID(ctx context.Context, runID string) ([]*model.StrategyRunArtifact, error) {
	var out []*model.StrategyRunArtifact
	if err := d.db.WithContext(ctx).Where("run_id = ?", strings.TrimSpace(runID)).Order("artifact_type ASC").Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}
