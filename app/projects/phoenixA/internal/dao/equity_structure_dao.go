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

// EquityStructureDao handles persistence for the equity_structure dataset
// (AmazingData get_equity_structure). Mirrors the financial_statement /
// corporate_action DAO pattern: BatchUpsert for writes, QueryFlat /
// QueryNested for dictionary-resolved reads.
type EquityStructureDao struct {
	*core.BaseComponent
	GormComp     *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	FieldDictDao *FieldDictionaryDao       `infra:"dep:dao_field_dictionary"`
	db           *gorm.DB
	dsName       string
}

func NewEquityStructureDao(dsName string) *EquityStructureDao {
	return &EquityStructureDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_EQUITY_STRUCTURE),
		dsName:        dsName,
	}
}

func (d *EquityStructureDao) Start(ctx context.Context) error {
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

func (d *EquityStructureDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// BatchUpsert upserts equity_structure rows. Unique key:
// (security_id, source, change_date, ann_date).
func (d *EquityStructureDao) BatchUpsert(ctx context.Context, list []*model.EquityStructure) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "security_id"}, {Name: "source"},
				{Name: "change_date"}, {Name: "ann_date"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"current_sign", "is_valid", "data_json", "updated_at",
			}),
		}).CreateInBatches(list, 200).Error
}

// applyEquityFilters returns the gorm query with equity_structure WHERE
// clauses applied. Shared between QueryFlat, QueryNested and Count. MUST return
// the *gorm.DB (gorm v2 Where returns a new session; callers must reassign:
// q = applyEquityFilters(q, f)).
func applyEquityFilters(q *gorm.DB, f *model.EquityStructureFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if f.SecurityID != 0 {
		q = q.Where("security_id = ?", f.SecurityID)
	}
	if len(f.SecurityIDs) > 0 {
		q = q.Where("security_id IN ?", f.SecurityIDs)
	}
	if f.ChangeDate != "" {
		q = q.Where("change_date = ?", f.ChangeDate)
	}
	if f.ChangeStart != "" {
		q = q.Where("change_date >= ?", f.ChangeStart)
	}
	if f.ChangeEnd != "" {
		q = q.Where("change_date <= ?", f.ChangeEnd)
	}
	if f.AnnDateBefore != "" {
		q = q.Where("ann_date < ?", f.AnnDateBefore)
	}
	if f.CurrentOnly {
		q = q.Where("current_sign = 1")
	}
	if f.ValidOnly {
		q = q.Where("is_valid = 1")
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

// Count returns the number of rows matching the filters.
func (d *EquityStructureDao) Count(ctx context.Context, source string, f *model.EquityStructureFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Table("ods.equity_structure").Where("source = ?", source)
	q = applyEquityFilters(q, f)
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}

// ResolveQueryFields resolves user-supplied field names against the field
// dictionary for the equity_structure dataset. dataType is always
// "equity_structure" (the dataset has a single data_type).
func (d *EquityStructureDao) ResolveQueryFields(ctx context.Context, source, dataType string, requested []string) ([]ResolvedField, []model.UnknownFieldHint, error) {
	return d.FieldDictDao.ResolveFields(ctx, source, "equity_structure", dataType, requested)
}

// QueryFlat runs a flat query against equity_structure. See
// FinancialStatementDao.QueryFlat for semantics.
func (d *EquityStructureDao) QueryFlat(ctx context.Context, source string, f *model.EquityStructureFilters, resolved []ResolvedField, limit, offset int) ([]map[string]any, error) {
	selectClause, _ := BuildFlatSelect(resolved)
	q := d.db.WithContext(ctx).Table("ods.equity_structure").Where("source = ?", source)
	q = applyEquityFilters(q, f)
	q = q.Order("security_id ASC, change_date DESC")
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

// QueryNested runs a nested query against equity_structure. See
// FinancialStatementDao.QueryNested for semantics.
func (d *EquityStructureDao) QueryNested(ctx context.Context, source string, f *model.EquityStructureFilters, resolved []ResolvedField, limit, offset int) ([]model.NestedRow, error) {
	topLevel, dataJSONFields := SplitResolved(resolved)

	selectParts := []string{
		"security_id", "source", "ann_date", "change_date",
		"current_sign", "is_valid",
	}
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
		Table("equity_structure").
		Select(strings.Join(selectParts, ", ")).
		Where("source = ?", source)
	q = applyEquityFilters(q, f)
	q = q.Order("security_id ASC, change_date DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}

	type rawNestedRow struct {
		SecurityID  uint64 `gorm:"column:security_id"`
		Source      string `gorm:"column:source"`
		AnnDate     string `gorm:"column:ann_date"`
		ChangeDate  string `gorm:"column:change_date"`
		CurrentSign int    `gorm:"column:current_sign"`
		IsValid     int    `gorm:"column:is_valid"`
		DataJSON    []byte `gorm:"column:data_json"`
	}
	var rawRows []rawNestedRow
	if err := q.Scan(&rawRows).Error; err != nil {
		return nil, err
	}

	rows := make([]model.NestedRow, 0, len(rawRows))
	for _, r := range rawRows {
		row := model.NestedRow{
			TopLevel: map[string]any{
				"security_id":  r.SecurityID,
				"source":       r.Source,
				"ann_date":     r.AnnDate,
				"change_date":  r.ChangeDate,
				"current_sign": r.CurrentSign,
				"is_valid":     r.IsValid,
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
