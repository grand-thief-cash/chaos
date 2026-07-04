package dao

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

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
	GormComp     *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	FieldDictDao *FieldDictionaryDao       `infra:"dep:dao_field_dictionary"`
	db           *gorm.DB
	dsName       string
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
// (security_id, source, statement_type, reporting_period, report_type, statement_code).
func (d *FinancialStatementDao) BatchUpsert(ctx context.Context, list []*model.FinancialStatement) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "security_id"}, {Name: "source"},
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
		Order("security_id ASC, reporting_period DESC")

	// Handle field selection
	if f != nil && len(f.Fields) > 0 {
		selectFields := make([]string, 0, len(f.Fields))
		for _, field := range f.Fields {
			// Handle JSONB nested fields: data_json.FIELD_NAME -> data_json->'FIELD_NAME'
			if strings.HasPrefix(field, "data_json.") {
				jsonField := strings.TrimPrefix(field, "data_json.")
				selectFields = append(selectFields, fmt.Sprintf("data_json->'%s' as %s", jsonField, field))
			} else {
				selectFields = append(selectFields, field)
			}
		}
		q = q.Select(selectFields)
	}

	if f != nil {
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.StatementType != "" {
			q = q.Where("statement_type = ?", f.StatementType)
		}
		if f.StatementCode != "" {
			q = q.Where("statement_code = ?", f.StatementCode)
		}
		if f.ReportingPeriod != "" {
			q = q.Where("reporting_period = ?", f.ReportingPeriod)
		}
		if len(f.ReportingPeriods) > 0 {
			q = q.Where("reporting_period IN ?", f.ReportingPeriods)
		}
		if f.PeriodStart != "" {
			q = q.Where("reporting_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("reporting_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
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
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.StatementType != "" {
			q = q.Where("statement_type = ?", f.StatementType)
		}
		if f.StatementCode != "" {
			q = q.Where("statement_code = ?", f.StatementCode)
		}
		if f.ReportingPeriod != "" {
			q = q.Where("reporting_period = ?", f.ReportingPeriod)
		}
		if len(f.ReportingPeriods) > 0 {
			q = q.Where("reporting_period IN ?", f.ReportingPeriods)
		}
		if f.PeriodStart != "" {
			q = q.Where("reporting_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("reporting_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
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

// applyFinStmtFilters returns the gorm query with financial-statement WHERE
// clauses applied. Shared between QueryFlat and QueryNested. MUST return the
// *gorm.DB (gorm v2 Where returns a new session; reassigning the local param
// would silently drop every filter — callers must reassign: q = applyFinStmtFilters(q, f)).
func applyFinStmtFilters(q *gorm.DB, f *model.FinancialStatementFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if f.SecurityID != 0 {
		q = q.Where("security_id = ?", f.SecurityID)
	}
	if len(f.SecurityIDs) > 0 {
		q = q.Where("security_id IN ?", f.SecurityIDs)
	}
	if f.StatementType != "" {
		q = q.Where("statement_type = ?", f.StatementType)
	}
	if f.StatementCode != "" {
		q = q.Where("statement_code = ?", f.StatementCode)
	}
	if f.ReportingPeriod != "" {
		q = q.Where("reporting_period = ?", f.ReportingPeriod)
	}
	if len(f.ReportingPeriods) > 0 {
		q = q.Where("reporting_period IN ?", f.ReportingPeriods)
	}
	if f.PeriodStart != "" {
		q = q.Where("reporting_period >= ?", f.PeriodStart)
	}
	if f.PeriodEnd != "" {
		q = q.Where("reporting_period <= ?", f.PeriodEnd)
	}
	if f.AnnDateBefore != "" {
		q = q.Where("ann_date < ?", f.AnnDateBefore)
	}
	if f.ReportType != "" {
		q = q.Where("report_type = ?", f.ReportType)
	}
	if f.CompTypeCode != nil {
		q = q.Where("comp_type_code = ?", *f.CompTypeCode)
	}
	if len(f.DataContains) > 0 {
		if jsonBytes, err := json.Marshal(f.DataContains); err == nil {
			q = q.Where("data_json @> ?::jsonb", string(jsonBytes))
		}
	}
	if f.DataHasKey != "" {
		q = q.Where("data_json ?? ?", f.DataHasKey)
	}
	return q
}

// ResolveQueryFields resolves user-supplied field names against the field
// dictionary for the financial_statement dataset. dataType is the
// statement_type (balance_sheet / income / cashflow / ...). Returns resolved
// fields plus unknown-field hints; the caller turns non-empty unknown into a
// 400 response.
func (d *FinancialStatementDao) ResolveQueryFields(ctx context.Context, source, dataType string, requested []string) ([]ResolvedField, []model.UnknownFieldHint, error) {
	return d.FieldDictDao.ResolveFields(ctx, source, "financial_statement", dataType, requested)
}

// QueryFlat runs a flat query: each resolved field becomes one column in a
// flat map. When resolved is empty, all top-level columns plus the full
// data_json are projected (callers asking for "*" semantics should pass an
// empty resolved list and use format=nested instead).
func (d *FinancialStatementDao) QueryFlat(ctx context.Context, source string, f *model.FinancialStatementFilters, resolved []ResolvedField, limit, offset int) ([]map[string]any, error) {
	selectClause, _ := BuildFlatSelect(resolved)
	q := d.db.WithContext(ctx).Table("ods.financial_statement").Where("source = ?", source)
	q = applyFinStmtFilters(q, f)
	q = q.Order("security_id ASC, reporting_period DESC")
	if selectClause != "" {
		q = q.Select(selectClause)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}

	var rows []map[string]any
	if err := q.Scan(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

// QueryNested runs a nested query: top-level columns go into the TopLevel
// map; data_json (full or filtered to requested keys) goes into the DataJSON
// map. When resolved is empty, the full data_json is returned.
func (d *FinancialStatementDao) QueryNested(ctx context.Context, source string, f *model.FinancialStatementFilters, resolved []ResolvedField, limit, offset int) ([]model.NestedRow, error) {
	topLevel, dataJSONFields := SplitResolved(resolved)

	// Build SELECT list: always include the canonical top-level columns that
	// make sense for nested output, plus any explicitly requested top_level
	// fields, plus either the full or filtered data_json.
	selectParts := []string{
		"security_id", "source", "statement_type", "reporting_period",
		"report_type", "statement_code", "security_name", "ann_date",
		"actual_ann_date", "comp_type_code",
	}
	// Add explicitly requested top_level fields not already in the list.
	seen := map[string]bool{}
	for _, p := range selectParts {
		seen[p] = true
	}
	for _, r := range topLevel {
		if r.SelectExpr != "" && !seen[r.OutputKey] {
			selectParts = append(selectParts, r.SelectExpr)
			seen[r.OutputKey] = true
		}
	}

	dataJSONExpr := "data_json"
	if filtered := BuildFilteredDataJSON(dataJSONFields); filtered != "" {
		dataJSONExpr = filtered
	}
	selectParts = append(selectParts, dataJSONExpr)

	q := d.db.WithContext(ctx).
		Table("financial_statement").
		Select(strings.Join(selectParts, ", ")).
		Where("source = ?", source)
	q = applyFinStmtFilters(q, f)
	q = q.Order("security_id ASC, reporting_period DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}

	type rawNestedRow struct {
		SecurityID      uint64 `gorm:"column:security_id"`
		Source          string `gorm:"column:source"`
		StatementType   string `gorm:"column:statement_type"`
		ReportingPeriod string `gorm:"column:reporting_period"`
		ReportType      string `gorm:"column:report_type"`
		StatementCode   string `gorm:"column:statement_code"`
		SecurityName    string `gorm:"column:security_name"`
		AnnDate         string `gorm:"column:ann_date"`
		ActualAnnDate   string `gorm:"column:actual_ann_date"`
		CompTypeCode    int    `gorm:"column:comp_type_code"`
		DataJSON        []byte `gorm:"column:data_json"`
	}
	var rawRows []rawNestedRow
	if err := q.Scan(&rawRows).Error; err != nil {
		return nil, err
	}

	rows := make([]model.NestedRow, 0, len(rawRows))
	for _, r := range rawRows {
		row := model.NestedRow{
			TopLevel: map[string]any{
				"security_id":      r.SecurityID,
				"source":           r.Source,
				"statement_type":   r.StatementType,
				"reporting_period": r.ReportingPeriod,
				"report_type":      r.ReportType,
				"statement_code":   r.StatementCode,
				"security_name":    r.SecurityName,
				"ann_date":         r.AnnDate,
				"actual_ann_date":  r.ActualAnnDate,
				"comp_type_code":   r.CompTypeCode,
			},
		}
		if len(r.DataJSON) > 0 && string(r.DataJSON) != "null" {
			var dj map[string]any
			if err := json.Unmarshal(r.DataJSON, &dj); err == nil {
				row.DataJSON = dj
			}
		}
		rows = append(rows, row)
	}
	return rows, nil
}
