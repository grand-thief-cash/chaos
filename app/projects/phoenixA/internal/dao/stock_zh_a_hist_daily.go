package dao

import (
	"context"
	"fmt"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/utils"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type StockZhAHistDaily struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewStockZhAHistDailyDao(dsName string) *StockZhAHistDaily {
	return &StockZhAHistDaily{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_STOCK_ZH_A_HIST_DAILY),
		dsName:        dsName,
	}
}

func (d *StockZhAHistDaily) Start(ctx context.Context) error {
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

func (d *StockZhAHistDaily) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *StockZhAHistDaily) BatchUpsert(ctx context.Context, upsertMeta *model.HistDataRequestMeta, data []*model.StockZhAHistDaily) error {

	tableName := getHistDataTableName(*upsertMeta.Period, *upsertMeta.Adjust)
	return d.db.Table(tableName).WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "date"}, {Name: "code"}},
			DoUpdates: clause.AssignmentColumns(
				[]string{"open", "high", "low", "close", "preclose",
					"volume", "amount", "turn", "pct_chg",
					"pe_ttm", "ps_ttm", "pcf_ncf_ttm", "pb_mrq"},
			),
		}).CreateInBatches(data, 1000).Error
}

func (d *StockZhAHistDaily) GetLatestUpdateByCodes(ctx context.Context, req *model.HistDataRequestMeta) (map[string]string, error) {

	tableName := getHistDataTableName(*req.Period, *req.Adjust)

	rows, err := d.db.Table(tableName).WithContext(ctx).
		Select("code, max(date) as last_date").
		Where("code IN ?", req.Codes).
		Group("code").
		Rows()
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()
	result := make(map[string]string)

	for rows.Next() {
		var code, date string
		if err = rows.Scan(&code, &date); err != nil {
			continue
		}
		result[code] = utils.NormalizedToYYYYMMDD(date)
	}

	return result, nil
}

func (d *StockZhAHistDaily) GetStockHist(ctx context.Context, req *model.HistDataRequestMeta) ([]*model.StockZhAHistDaily, error) {
	tableName := getHistDataTableName(*req.Period, *req.Adjust)

	q := d.db.Table(tableName).WithContext(ctx).
		Where("code = ? AND date >= ? AND date <= ?", req.Code, req.StartDate, req.EndDate).
		Order("date ASC")
	if len(req.Fields) > 0 {
		q = q.Select(req.Fields)
	}

	if req.Limit != nil {
		q = q.Limit(*req.Limit)
	}
	if req.Offset != nil {
		q = q.Offset(*req.Offset)
	}

	var out []*model.StockZhAHistDaily
	if err := q.Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}
