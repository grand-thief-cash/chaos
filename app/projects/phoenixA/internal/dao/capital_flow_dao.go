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

type CapitalFlowDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewCapitalFlowDao(dsName string) *CapitalFlowDao {
	return &CapitalFlowDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_CAPITAL_FLOW),
		dsName:        dsName,
	}
}

func (d *CapitalFlowDao) Start(ctx context.Context) error {
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

func (d *CapitalFlowDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *CapitalFlowDao) BatchUpsertMarginSummary(
	ctx context.Context, rows []*model.MarginSummaryDaily,
) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "trade_date"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"financing_balance", "financing_buy", "financing_repay",
			"securities_balance", "securities_sell_volume", "margin_total_balance",
		}),
	}).CreateInBatches(rows, 500).Error
}

func (d *CapitalFlowDao) BatchUpsertHSGT(
	ctx context.Context, rows []*model.HSGTDaily,
) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "symbol"}, {Name: "trade_date"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"net_buy", "buy_amount", "sell_amount", "cumulative_net_buy",
			"capital_inflow", "quota_balance", "holding_market_value",
			"leading_stock_name", "leading_stock_symbol", "leading_stock_pct_chg",
			"benchmark_value", "benchmark_pct_chg",
		}),
	}).CreateInBatches(rows, 500).Error
}

func (d *CapitalFlowDao) QueryMarginSummary(
	ctx context.Context, f *model.CapitalFlowFilters, limit, offset int,
) ([]*model.MarginSummaryDaily, error) {
	var rows []*model.MarginSummaryDaily
	q := d.db.WithContext(ctx).Model(&model.MarginSummaryDaily{})
	if f != nil {
		q = applyDateRange(q, f.StartDate, f.EndDate)
	}
	err := finishDailyDataQuery(q, limit, offset).Find(&rows).Error
	return rows, err
}

func (d *CapitalFlowDao) QueryHSGT(
	ctx context.Context, f *model.CapitalFlowFilters, limit, offset int,
) ([]*model.HSGTDaily, error) {
	var rows []*model.HSGTDaily
	q := d.db.WithContext(ctx).Model(&model.HSGTDaily{})
	if f != nil {
		q = applyDateRange(q, f.StartDate, f.EndDate)
		if len(f.Symbols) > 0 {
			q = q.Where("symbol IN ?", f.Symbols)
		}
	}
	err := finishDailyDataQuery(q.Order("symbol ASC"), limit, offset).
		Find(&rows).Error
	return rows, err
}

func (d *CapitalFlowDao) LastMarginSummaryDate(
	ctx context.Context,
) (string, error) {
	var last string
	err := d.db.WithContext(ctx).Model(&model.MarginSummaryDaily{}).
		Select("COALESCE(MAX(trade_date)::text, '')").
		Row().
		Scan(&last)
	return last, err
}

func (d *CapitalFlowDao) LastHSGTDates(
	ctx context.Context, symbols []string,
) (map[string]string, error) {
	return lastUpdatesByStringKey(
		ctx,
		d.db,
		&model.HSGTDaily{},
		"symbol",
		symbols,
	)
}
