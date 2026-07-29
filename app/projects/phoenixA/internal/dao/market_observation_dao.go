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

type MarketObservationDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewMarketObservationDao(dsName string) *MarketObservationDao {
	return &MarketObservationDao{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_DAO_MARKET_OBSERVATION,
		),
		dsName: dsName,
	}
}

func (d *MarketObservationDao) Start(ctx context.Context) error {
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

func (d *MarketObservationDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *MarketObservationDao) BatchUpsert(
	ctx context.Context, rows []*model.MarketObservationDaily,
) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{
			{Name: "security_id"},
			{Name: "trade_date"},
			{Name: "observation_type"},
			{Name: "source"},
		},
		DoUpdates: clause.AssignmentColumns([]string{
			"value", "unit", "extra_json",
		}),
	}).CreateInBatches(rows, 500).Error
}

func (d *MarketObservationDao) Query(
	ctx context.Context,
	source string,
	f *model.MarketObservationFilters,
	limit, offset int,
) ([]*model.MarketObservationDaily, error) {
	var rows []*model.MarketObservationDaily
	q := d.db.WithContext(ctx).
		Model(&model.MarketObservationDaily{}).
		Where("source = ?", source)
	if f != nil {
		q = applyDateRange(q, f.StartDate, f.EndDate)
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if len(f.ObservationTypes) > 0 {
			q = q.Where("observation_type IN ?", f.ObservationTypes)
		}
	}
	err := finishDailyDataQuery(
		q.Order("security_id ASC").Order("observation_type ASC"),
		limit,
		offset,
	).Find(&rows).Error
	return rows, err
}

type observationLastUpdate struct {
	SecurityID uint64 `gorm:"column:security_id"`
	LastUpdate string `gorm:"column:last_update"`
}

func (d *MarketObservationDao) LastDates(
	ctx context.Context,
	source string,
	securityIDs []uint64,
) (map[uint64]string, error) {
	var rows []observationLastUpdate
	q := d.db.WithContext(ctx).
		Model(&model.MarketObservationDaily{}).
		Select("security_id, MAX(trade_date)::text AS last_update").
		Where("source = ?", source).
		Group("security_id")
	if len(securityIDs) > 0 {
		q = q.Where("security_id IN ?", securityIDs)
	}
	if err := q.Scan(&rows).Error; err != nil {
		return nil, err
	}
	result := make(map[uint64]string, len(rows))
	for _, row := range rows {
		result[row.SecurityID] = row.LastUpdate
	}
	return result, nil
}
