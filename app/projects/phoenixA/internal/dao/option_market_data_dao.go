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

type OptionMarketDataDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewOptionMarketDataDao(dsName string) *OptionMarketDataDao {
	return &OptionMarketDataDao{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_DAO_OPTION_MARKET_DATA,
		),
		dsName: dsName,
	}
}

func (d *OptionMarketDataDao) Start(ctx context.Context) error {
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

func (d *OptionMarketDataDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *OptionMarketDataDao) BatchUpsertOptionQVIX(
	ctx context.Context, rows []*model.OptionQVIXDaily,
) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "symbol"}, {Name: "trade_date"}},
		DoUpdates: clause.AssignmentColumns([]string{"open", "high", "low", "close"}),
	}).CreateInBatches(rows, 500).Error
}

func (d *OptionMarketDataDao) BatchUpsertOptionDailyStats(
	ctx context.Context, rows []*model.OptionDailyStats,
) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{
			{Name: "exchange"}, {Name: "underlying_symbol"}, {Name: "trade_date"},
		},
		DoUpdates: clause.AssignmentColumns([]string{
			"underlying_name", "contract_count", "turnover", "volume",
			"call_volume", "put_volume", "put_call_volume_ratio", "open_interest",
			"call_open_interest", "put_open_interest", "put_call_open_interest_ratio",
		}),
	}).CreateInBatches(rows, 500).Error
}

func (d *OptionMarketDataDao) QueryOptionQVIX(
	ctx context.Context, f *model.OptionMarketDataFilters, limit, offset int,
) ([]*model.OptionQVIXDaily, error) {
	var rows []*model.OptionQVIXDaily
	q := d.db.WithContext(ctx).Model(&model.OptionQVIXDaily{})
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

func (d *OptionMarketDataDao) QueryOptionDailyStats(
	ctx context.Context, f *model.OptionMarketDataFilters, limit, offset int,
) ([]*model.OptionDailyStats, error) {
	var rows []*model.OptionDailyStats
	q := d.db.WithContext(ctx).Model(&model.OptionDailyStats{})
	if f != nil {
		q = applyDateRange(q, f.StartDate, f.EndDate)
		if len(f.Exchanges) > 0 {
			q = q.Where("exchange IN ?", f.Exchanges)
		}
	}
	err := finishDailyDataQuery(
		q.Order("exchange ASC").Order("underlying_symbol ASC"),
		limit,
		offset,
	).Find(&rows).Error
	return rows, err
}

func (d *OptionMarketDataDao) LastOptionQVIXDates(
	ctx context.Context, symbols []string,
) (map[string]string, error) {
	return lastUpdatesByStringKey(
		ctx,
		d.db,
		&model.OptionQVIXDaily{},
		"symbol",
		symbols,
	)
}

func (d *OptionMarketDataDao) LastOptionDailyStatsDates(
	ctx context.Context, exchanges []string,
) (map[string]string, error) {
	return lastUpdatesByStringKey(
		ctx,
		d.db,
		&model.OptionDailyStats{},
		"exchange",
		exchanges,
	)
}
