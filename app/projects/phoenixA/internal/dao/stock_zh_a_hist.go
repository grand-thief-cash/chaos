package dao

import (
	"context"
	"fmt"
	"strings"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
)

type StockZhAHistDao interface {
	core.Component
	BatchSaveDaily(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistDaily) error
	BatchSaveWeeklyMonthly(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistWeeklyMonthly) error
	BatchSaveMin(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistMin) error
	GetLatestDateBatch(ctx context.Context, frequency, adjust string) (map[string]string, error)
	GetLatestDateByCodes(ctx context.Context, frequency, adjust string, codes []string) (map[string]string, error)
	GetStockHist(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int) ([]*model.StockZhAHistDaily, error)
	// GetStockHistSelected returns daily bars for a single code within [startDate, endDate], selecting only requested fields.
	// fields are JSON field names (e.g. date, open, close). date will be auto-included.
	GetStockHistSelected(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int, fields []string) ([]*model.StockZhAHistDaily, error)
}

type stockZhAHistDaoImpl struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewStockZhAHistDao(dsName string) StockZhAHistDao {
	return &stockZhAHistDaoImpl{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_STOCK_ZH_A_HIST, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

func (d *stockZhAHistDaoImpl) Start(ctx context.Context) error {
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

func (d *stockZhAHistDaoImpl) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// getTableName constructs the dynamic table name.
// adjust: qfq (1), hfq (2), nf (3)
func (d *stockZhAHistDaoImpl) getTableName(frequency, adjust string) string {
	adjMap := map[string]string{
		"1": "hfq",
		"2": "qfq",
		"3": "nf",
		// Support string inputs too
		"hfq": "hfq",
		"qfq": "qfq",
		"nf":  "nf",
	}

	adjStr, ok := adjMap[adjust]
	if !ok {
		adjStr = "nf" // Default
	}

	freqStr := frequency

	// Map frequency to table part
	switch frequency {
	case "d", "daily":
		freqStr = "daily"
	case "w", "weekly":
		freqStr = "weekly"
	case "m", "monthly":
		freqStr = "monthly"
	default:
		// 5, 15, 30, 60 -> min5, min15, min30, min60
		if strings.HasPrefix(frequency, "min") {
			freqStr = frequency
		} else {
			// check for numeric minutes
			if frequency == "5" || frequency == "15" || frequency == "30" || frequency == "60" {
				freqStr = "min" + frequency
			}
		}
	}

	return fmt.Sprintf("stock_zh_a_hist_%s_%s", freqStr, adjStr)
}

// ensureTable is no longer needed to migrate, as migration is done via SQL.
// But we can check if it exists if needed. For now, trusting the migration.

func (d *stockZhAHistDaoImpl) BatchSaveDaily(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistDaily) error {
	if len(data) == 0 {
		return nil
	}
	tableName := d.getTableName(frequency, adjust)
	return d.db.Table(tableName).WithContext(ctx).CreateInBatches(data, 1000).Error
}

func (d *stockZhAHistDaoImpl) BatchSaveWeeklyMonthly(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistWeeklyMonthly) error {
	_ = ctx
	_ = frequency
	_ = adjust
	_ = data
	// Temporarily disabled for this iteration as requested
	return nil
}

func (d *stockZhAHistDaoImpl) BatchSaveMin(ctx context.Context, frequency, adjust string, data []*model.StockZhAHistMin) error {
	_ = ctx
	_ = frequency
	_ = adjust
	_ = data
	// Temporarily disabled for this iteration as requested
	return nil
}

func (d *stockZhAHistDaoImpl) GetLatestDateBatch(ctx context.Context, frequency, adjust string) (map[string]string, error) {
	tableName := d.getTableName(frequency, adjust)
	// We assume table exists because migration is handled by framework

	rows, err := d.db.Table(tableName).WithContext(ctx).
		Select("code, max(date) as last_date").
		Group("code").
		Rows()
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()

	result := make(map[string]string)
	for rows.Next() {
		var code, date string
		if err := rows.Scan(&code, &date); err != nil {
			continue
		}
		result[code] = date
	}
	return result, nil
}

func (d *stockZhAHistDaoImpl) GetLatestDateByCodes(ctx context.Context, frequency, adjust string, codes []string) (map[string]string, error) {
	if len(codes) == 0 {
		return map[string]string{}, nil
	}

	tableName := d.getTableName(frequency, adjust)

	rows, err := d.db.Table(tableName).WithContext(ctx).
		Select("code, max(date) as last_date").
		Where("code IN ?", codes).
		Group("code").
		Rows()
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()

	result := make(map[string]string)
	for rows.Next() {
		var code, date string
		if err := rows.Scan(&code, &date); err != nil {
			continue
		}
		result[code] = date
	}
	return result, nil
}

func (d *stockZhAHistDaoImpl) GetStockHist(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int) ([]*model.StockZhAHistDaily, error) {
	return d.GetStockHistSelected(ctx, frequency, adjust, code, startDate, endDate, limit, offset, nil)
}

func (d *stockZhAHistDaoImpl) GetStockHistSelected(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int, fields []string) ([]*model.StockZhAHistDaily, error) {
	tableName := d.getTableName(frequency, adjust)

	selectCols := make([]string, 0, len(fields)+1)
	seen := make(map[string]struct{})
	addCol := func(col string) {
		if col == "" {
			return
		}
		if _, ok := seen[col]; ok {
			return
		}
		seen[col] = struct{}{}
		selectCols = append(selectCols, col)
	}

	// Always include date
	addCol("date")

	// Map json field -> db column
	toDBCol := func(f string) string {
		switch f {
		case "date":
			return "date"
		case "code":
			return "code"
		case "open", "high", "low", "close", "preclose", "volume", "amount", "turn":
			return f
		case "pctChg":
			return "pct_chg"
		case "peTTM":
			return "pe_ttm"
		case "psTTM":
			return "ps_ttm"
		case "pcfNcfTTM":
			return "pcf_ncf_ttm"
		case "pbMRQ":
			return "pb_mrq"
		default:
			return ""
		}
	}

	for _, f := range fields {
		f = strings.TrimSpace(f)
		if f == "" {
			continue
		}
		addCol(toDBCol(f))
	}

	q := d.db.Table(tableName).WithContext(ctx).
		Where("code = ? AND date >= ? AND date <= ?", code, startDate, endDate).
		Order("date ASC")

	if len(selectCols) > 0 {
		q = q.Select(strings.Join(selectCols, ","))
	}

	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}

	var out []*model.StockZhAHistDaily
	if err := q.Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}
