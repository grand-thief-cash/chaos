package dao

import (
	"context"
	"fmt"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/utils"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// BarsDao is the unified DAO for standard bars data across all asset types.
// Table names are resolved dynamically via BarsTableName().
type BarsDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewBarsDao(dsName string) *BarsDao {
	return &BarsDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_BARS),
		dsName:        dsName,
	}
}

func (d *BarsDao) Start(ctx context.Context) error {
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

func (d *BarsDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsert writes standard bars into the dynamic table.
func (d *BarsDao) BatchUpsert(ctx context.Context, q *model.BarsQuery, bars []*model.StandardBar) error {
	tableName := BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	return d.db.Table(tableName).WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "symbol"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns(
				[]string{"open", "high", "low", "close", "volume", "amount", "preclose", "pct_chg"},
			),
		}).CreateInBatches(bars, 1000).Error
}

// GetLatestUpdateBySymbols returns map[symbol]lastTradeDate for the given symbols.
func (d *BarsDao) GetLatestUpdateBySymbols(ctx context.Context, q *model.BarsQuery) (map[string]string, error) {
	tableName := BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	rows, err := d.db.Table(tableName).WithContext(ctx).
		Select("symbol, MAX(trade_date) as last_date").
		Where("symbol IN ?", q.Symbols).
		Group("symbol").
		Rows()
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()

	result := make(map[string]string)
	for rows.Next() {
		var symbol, date string
		if err = rows.Scan(&symbol, &date); err != nil {
			continue
		}
		result[symbol] = utils.NormalizedToYYYYMMDD(date)
	}
	return result, nil
}

// QueryBars returns bars for a single symbol within [startDate, endDate].
func (d *BarsDao) QueryBars(ctx context.Context, q *model.BarsQuery) ([]*model.StandardBar, error) {
	tableName := BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	db := d.db.Table(tableName).WithContext(ctx).
		Where("symbol = ? AND trade_date >= ? AND trade_date <= ?", q.Symbol, q.StartDate, q.EndDate).
		Order("trade_date ASC")

	if len(q.Fields) > 0 {
		db = db.Select(q.Fields)
	}
	if q.Limit > 0 {
		db = db.Limit(q.Limit)
	}
	if q.Offset > 0 {
		db = db.Offset(q.Offset)
	}

	var out []*model.StandardBar
	if err := db.Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}

// BatchUpsertExt writes extension bars data into the source-specific extension table.
func (d *BarsDao) BatchUpsertExt(ctx context.Context, source string, q *model.BarsQuery, data []*model.BarsExtBaostock) error {
	tableName := BarsExtTableName(source, q.AssetType, q.Market, q.Period)
	return d.db.Table(tableName).WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "symbol"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns(
				[]string{"turn", "pe_ttm", "ps_ttm", "pb_mrq", "pcf_ncf_ttm"},
			),
		}).CreateInBatches(data, 1000).Error
}
