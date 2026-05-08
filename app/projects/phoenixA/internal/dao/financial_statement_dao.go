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

// FinancialStatementDao handles persistence for financial statement data.
type FinancialStatementDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewFinancialStatementDao(dsName string) *FinancialStatementDao {
	return &FinancialStatementDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_FINANCIAL_STMT),
		dsName:        dsName,
	}
}

func (d *FinancialStatementDao) Start(ctx context.Context) error {
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

func (d *FinancialStatementDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsert upserts financial statements. The unique key is
// (source, symbol, market, statement_type, reporting_period, report_type, statement_code).
func (d *FinancialStatementDao) BatchUpsert(ctx context.Context, list []*model.FinancialStatement) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "source"}, {Name: "symbol"}, {Name: "market"},
				{Name: "statement_type"}, {Name: "reporting_period"},
				{Name: "report_type"}, {Name: "statement_code"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"security_name", "ann_date", "actual_ann_date",
				"comp_type_code", "data_json", "updated_at",
			}),
		}).CreateInBatches(list, 200).Error
}

// Query returns financial statements matching the given filters.
func (d *FinancialStatementDao) Query(ctx context.Context, source string, f *model.FinancialStatementFilters, limit, offset int) ([]*model.FinancialStatement, error) {
	var list []*model.FinancialStatement
	q := d.db.WithContext(ctx).Model(&model.FinancialStatement{}).
		Where("source = ?", source).
		Order("symbol ASC, reporting_period DESC")

	if f != nil {
		if f.Symbol != "" {
			q = q.Where("symbol = ?", f.Symbol)
		}
		if f.Market != "" {
			q = q.Where("market = ?", f.Market)
		}
		if f.StatementType != "" {
			q = q.Where("statement_type = ?", f.StatementType)
		}
		if f.ReportingPeriod != "" {
			q = q.Where("reporting_period = ?", f.ReportingPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("reporting_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("reporting_period <= ?", f.PeriodEnd)
		}
		if f.ReportType != "" {
			q = q.Where("report_type = ?", f.ReportType)
		}
		if f.CompTypeCode != nil {
			q = q.Where("comp_type_code = ?", *f.CompTypeCode)
		}
		// PostgreSQL JSONB containment: data_json @> '{"TOTAL_ASSETS": 1000000}'
		if len(f.DataContains) > 0 {
			jsonBytes, err := json.Marshal(f.DataContains)
			if err == nil {
				q = q.Where("data_json @> ?::jsonb", string(jsonBytes))
			}
		}
		// PostgreSQL JSONB key existence: data_json ? 'TOTAL_ASSETS'
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

// Count returns the count of financial statements matching the given filters.
func (d *FinancialStatementDao) Count(ctx context.Context, source string, f *model.FinancialStatementFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.FinancialStatement{}).Where("source = ?", source)
	if f != nil {
		if f.Symbol != "" {
			q = q.Where("symbol = ?", f.Symbol)
		}
		if f.Market != "" {
			q = q.Where("market = ?", f.Market)
		}
		if f.StatementType != "" {
			q = q.Where("statement_type = ?", f.StatementType)
		}
		if f.ReportingPeriod != "" {
			q = q.Where("reporting_period = ?", f.ReportingPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("reporting_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("reporting_period <= ?", f.PeriodEnd)
		}
		if f.ReportType != "" {
			q = q.Where("report_type = ?", f.ReportType)
		}
		if f.CompTypeCode != nil {
			q = q.Where("comp_type_code = ?", *f.CompTypeCode)
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
