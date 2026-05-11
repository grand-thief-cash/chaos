package dao

import (
	"context"
	"encoding/json"
	"fmt"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// CorporateActionDao handles persistence for corporate action data.
type CorporateActionDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewCorporateActionDao(dsName string) *CorporateActionDao {
	return &CorporateActionDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_CORP_ACTION),
		dsName:        dsName,
	}
}

func (d *CorporateActionDao) Start(ctx context.Context) error {
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

func (d *CorporateActionDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsert upserts corporate actions. Unique key:
// (source, symbol, market, action_type, report_period, ann_date).
func (d *CorporateActionDao) BatchUpsert(ctx context.Context, list []*model.CorporateAction) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "source"}, {Name: "symbol"}, {Name: "market"},
				{Name: "action_type"}, {Name: "report_period"}, {Name: "ann_date"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"progress_code", "data_json", "updated_at",
			}),
		}).CreateInBatches(list, 200).Error
}

// Query returns corporate actions matching the given filters.
func (d *CorporateActionDao) Query(ctx context.Context, source string, f *model.CorporateActionFilters, limit, offset int) ([]*model.CorporateAction, error) {
	var list []*model.CorporateAction
	q := d.db.WithContext(ctx).Model(&model.CorporateAction{}).
		Where("source = ?", source).
		Order("symbol ASC, report_period DESC, ann_date DESC")

	if f != nil {
		if f.Symbol != "" {
			q = q.Where("symbol = ?", f.Symbol)
		}
		if f.Market != "" {
			q = q.Where("market = ?", f.Market)
		}
		if f.ActionType != "" {
			q = q.Where("action_type = ?", f.ActionType)
		}
		if f.ReportPeriod != "" {
			q = q.Where("report_period = ?", f.ReportPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("report_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("report_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
		}
		if f.ProgressCode != "" {
			q = q.Where("progress_code = ?", f.ProgressCode)
		}
		// PostgreSQL JSONB containment: data_json @> '{"key": value}'
		if len(f.DataContains) > 0 {
			jsonBytes, err := json.Marshal(f.DataContains)
			if err == nil {
				q = q.Where("data_json @> ?::jsonb", string(jsonBytes))
			}
		}
		// PostgreSQL JSONB key existence: data_json ? 'key'
		if f.DataHasKey != "" {
			q = q.Where("data_json ?? ?", f.DataHasKey)
		}
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

// Count returns the count of corporate actions matching the given filters.
func (d *CorporateActionDao) Count(ctx context.Context, source string, f *model.CorporateActionFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.CorporateAction{}).Where("source = ?", source)
	if f != nil {
		if f.Symbol != "" {
			q = q.Where("symbol = ?", f.Symbol)
		}
		if f.Market != "" {
			q = q.Where("market = ?", f.Market)
		}
		if f.ActionType != "" {
			q = q.Where("action_type = ?", f.ActionType)
		}
		if f.ReportPeriod != "" {
			q = q.Where("report_period = ?", f.ReportPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("report_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("report_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
		}
		if f.ProgressCode != "" {
			q = q.Where("progress_code = ?", f.ProgressCode)
		}
		if len(f.DataContains) > 0 {
			jsonBytes, err := json.Marshal(f.DataContains)
			if err == nil {
				q = q.Where("data_json @> ?::jsonb", string(jsonBytes))
			}
		}
		if f.DataHasKey != "" {
			q = q.Where("data_json ?? ?", f.DataHasKey)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}
