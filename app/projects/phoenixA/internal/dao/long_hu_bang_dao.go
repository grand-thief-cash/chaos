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

// LongHuBangDao handles persistence for long hu bang data.
type LongHuBangDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewLongHuBangDao(dsName string) *LongHuBangDao {
	return &LongHuBangDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_LONG_HU_BANG),
		dsName:        dsName,
	}
}

func (d *LongHuBangDao) Start(ctx context.Context) error {
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

func (d *LongHuBangDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *LongHuBangDao) BatchUpsert(ctx context.Context, list []*model.LongHuBang) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "security_id"}, {Name: "source"},
				{Name: "trade_date"}, {Name: "reason_type"}, {Name: "trader_name"}, {Name: "flow_mark"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"security_name", "reason_type_name", "change_range", "buy_amount", "sell_amount", "total_amount", "total_volume", "updated_at",
			}),
		}).CreateInBatches(list, 200).Error
}

func (d *LongHuBangDao) Query(ctx context.Context, source string, f *model.LongHuBangFilters, limit, offset int) ([]*model.LongHuBang, error) {
	var list []*model.LongHuBang
	q := d.db.WithContext(ctx).Model(&model.LongHuBang{}).
		Where("source = ?", source).
		Order("trade_date DESC, security_id ASC, reason_type ASC, trader_name ASC, flow_mark ASC")

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
		if f.TradeDate != "" {
			q = q.Where("trade_date = ?", f.TradeDate)
		}
		if f.StartDate != "" {
			q = q.Where("trade_date >= ?", f.StartDate)
		}
		if f.EndDate != "" {
			q = q.Where("trade_date <= ?", f.EndDate)
		}
		if f.ReasonType != "" {
			q = q.Where("reason_type = ?", f.ReasonType)
		}
		if f.TraderName != "" {
			q = q.Where("trader_name = ?", f.TraderName)
		}
		if f.FlowMark != nil {
			q = q.Where("flow_mark = ?", *f.FlowMark)
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

func (d *LongHuBangDao) Count(ctx context.Context, source string, f *model.LongHuBangFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.LongHuBang{}).Where("source = ?", source)
	if f != nil {
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.TradeDate != "" {
			q = q.Where("trade_date = ?", f.TradeDate)
		}
		if f.StartDate != "" {
			q = q.Where("trade_date >= ?", f.StartDate)
		}
		if f.EndDate != "" {
			q = q.Where("trade_date <= ?", f.EndDate)
		}
		if f.ReasonType != "" {
			q = q.Where("reason_type = ?", f.ReasonType)
		}
		if f.TraderName != "" {
			q = q.Where("trader_name = ?", f.TraderName)
		}
		if f.FlowMark != nil {
			q = q.Where("flow_mark = ?", *f.FlowMark)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}
