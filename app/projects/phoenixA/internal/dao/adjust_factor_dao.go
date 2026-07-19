package dao

import (
	"context"
	"fmt"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// AdjustFactorDao handles persistence for adjust factor data.
type AdjustFactorDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewAdjustFactorDao(dsName string) *AdjustFactorDao {
	return &AdjustFactorDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_ADJUST_FACTOR),
		dsName:        dsName,
	}
}

func (d *AdjustFactorDao) Start(ctx context.Context) error {
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

func (d *AdjustFactorDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *AdjustFactorDao) BatchUpsert(ctx context.Context, list []*model.AdjustFactor) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "security_id"}, {Name: "source"}, {Name: "divid_operate_date"}},
			DoUpdates: clause.AssignmentColumns([]string{
				"fore_adjust_factor", "back_adjust_factor", "adjust_factor",
			}),
		}).CreateInBatches(list, 500).Error
}

func (d *AdjustFactorDao) Query(ctx context.Context, source string, f *model.AdjustFactorFilters, limit, offset int) ([]*model.AdjustFactor, error) {
	var list []*model.AdjustFactor
	q := d.db.WithContext(ctx).Model(&model.AdjustFactor{}).
		Where("source = ?", source).
		Order("security_id ASC, divid_operate_date DESC")

	if f != nil && len(f.Fields) > 0 {
		q = q.Select(f.Fields)
	}

	if f != nil {
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.StartDate != "" {
			q = q.Where("divid_operate_date >= ?", f.StartDate)
		}
		if f.EndDate != "" {
			q = q.Where("divid_operate_date <= ?", f.EndDate)
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

func (d *AdjustFactorDao) Count(ctx context.Context, source string, f *model.AdjustFactorFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.AdjustFactor{}).Where("source = ?", source)
	if f != nil {
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.StartDate != "" {
			q = q.Where("divid_operate_date >= ?", f.StartDate)
		}
		if f.EndDate != "" {
			q = q.Where("divid_operate_date <= ?", f.EndDate)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}
