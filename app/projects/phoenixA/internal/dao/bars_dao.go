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
			Columns: []clause.Column{{Name: "security_id"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns(
				[]string{"open", "high", "low", "close", "volume", "amount", "preclose", "pct_chg"},
			),
		}).CreateInBatches(bars, 1000).Error
}

// GetLatestUpdateBySecurityIDs returns map[security_id]lastTradeDate.
func (d *BarsDao) GetLatestUpdateBySecurityIDs(ctx context.Context, q *model.BarsQuery) (map[uint64]string, error) {
	tableName := BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	rows, err := d.db.Table(tableName).WithContext(ctx).
		Select("security_id, MAX(trade_date) as last_date").
		Where("security_id IN ?", q.SecurityIDs).
		Group("security_id").
		Rows()
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()

	result := make(map[uint64]string)
	for rows.Next() {
		var securityID uint64
		var date string
		if err = rows.Scan(&securityID, &date); err != nil {
			continue
		}
		if bizConsts.IsIntradayPeriod(q.Period) {
			result[securityID] = date
		} else {
			result[securityID] = utils.NormalizedToYYYYMMDD(date)
		}
	}
	return result, nil
}

// QueryBars returns bars for one registered security within the range.
func (d *BarsDao) QueryBars(ctx context.Context, q *model.BarsQuery) ([]*model.StandardBar, error) {
	tableName := BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
	db := d.db.Table(tableName).WithContext(ctx).
		Where("security_id = ? AND trade_date >= ? AND trade_date <= ?", q.SecurityID, q.StartDate, q.EndDate).
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

// BatchUpsertExt writes non-canonical fields into the requested extension schema.
func (d *BarsDao) BatchUpsertExt(ctx context.Context, extensionKind string, q *model.BarsQuery, data []*model.BarsExtBaostock) error {
	tableName := BarsExtTableName(extensionKind, q.AssetType, q.Market, q.Period)
	return d.db.Table(tableName).WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "security_id"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns(
				[]string{"turn", "pe_ttm", "ps_ttm", "pb_mrq", "pcf_ncf_ttm", "trade_status", "is_st"},
			),
		}).CreateInBatches(data, 1000).Error
}
