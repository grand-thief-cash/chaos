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

// CorporateActionDao handles persistence for corporate action data.
type CorporateActionDao struct {
	*core.BaseComponent
	GormComp     *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	FieldDictDao *FieldDictionaryDao       `infra:"dep:dao_field_dictionary"`
	db           *gorm.DB
	dsName       string
}

func NewCorporateActionDao(dsName string) *CorporateActionDao {
	return &CorporateActionDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_CORP_ACTION),
		dsName:        dsName,
	}
}

func (d *CorporateActionDao) Start(ctx context.Context) error {
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

func (d *CorporateActionDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsert upserts corporate actions. Unique key:
// (security_id, source, action_type, report_period, ann_date).
func (d *CorporateActionDao) BatchUpsert(ctx context.Context, list []*model.CorporateAction) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "security_id"}, {Name: "source"},
				{Name: "action_type"}, {Name: "report_period"}, {Name: "ann_date"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"progress_code", "data_json", "updated_at",
			}),
		}).CreateInBatches(list, 200).Error
}

// Query returns corporate actions matching the given filters.
func (d *CorporateActionDao) Query(ctx context.Context, source string, f *model.CorporateActionFilters, limit, offset int) ([]*model.CorporateAction, error) {
	var list []*model.CorporateAction
	q := d.db.WithContext(ctx).Model(&model.CorporateAction{}).
		Where("source = ?", source).
		Order("security_id ASC, report_period DESC, ann_date DESC")

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
		if f.ActionType != "" {
			q = q.Where("action_type = ?", f.ActionType)
		}
		if f.ReportPeriod != "" {
			q = q.Where("report_period = ?", f.ReportPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("report_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("report_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
		}
		if f.ProgressCode != "" {
			q = q.Where("progress_code = ?", f.ProgressCode)
		}
		// PostgreSQL JSONB containment: data_json @> '{"key": value}'
		if len(f.DataContains) > 0 {
			jsonBytes, err := json.Marshal(f.DataContains)
			if err == nil {
				q = q.Where("data_json @> ?::jsonb", string(jsonBytes))
			}
		}
		// PostgreSQL JSONB key existence: data_json ? 'key'
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

// Count returns the count of corporate actions matching the given filters.
func (d *CorporateActionDao) Count(ctx context.Context, source string, f *model.CorporateActionFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.CorporateAction{}).Where("source = ?", source)
	if f != nil {
		if f.SecurityID != 0 {
			q = q.Where("security_id = ?", f.SecurityID)
		}
		if len(f.SecurityIDs) > 0 {
			q = q.Where("security_id IN ?", f.SecurityIDs)
		}
		if f.ActionType != "" {
			q = q.Where("action_type = ?", f.ActionType)
		}
		if f.ReportPeriod != "" {
			q = q.Where("report_period = ?", f.ReportPeriod)
		}
		if f.PeriodStart != "" {
			q = q.Where("report_period >= ?", f.PeriodStart)
		}
		if f.PeriodEnd != "" {
			q = q.Where("report_period <= ?", f.PeriodEnd)
		}
		if f.AnnDateBefore != "" {
			q = q.Where("ann_date < ?", f.AnnDateBefore)
		}
		if f.ProgressCode != "" {
			q = q.Where("progress_code = ?", f.ProgressCode)
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

// applyCorpActionFilters returns the gorm query with corporate-action WHERE
// clauses applied. Shared between QueryFlat and QueryNested. MUST return the
// *gorm.DB (gorm v2 Where returns a new session; callers must reassign:
// q = applyCorpActionFilters(q, f)).
func applyCorpActionFilters(q *gorm.DB, f *model.CorporateActionFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if f.SecurityID != 0 {
		q = q.Where("security_id = ?", f.SecurityID)
	}
	if len(f.SecurityIDs) > 0 {
		q = q.Where("security_id IN ?", f.SecurityIDs)
	}
	if f.ActionType != "" {
		q = q.Where("action_type = ?", f.ActionType)
	}
	if f.ReportPeriod != "" {
		q = q.Where("report_period = ?", f.ReportPeriod)
	}
	if f.PeriodStart != "" {
		q = q.Where("report_period >= ?", f.PeriodStart)
	}
	if f.PeriodEnd != "" {
		q = q.Where("report_period <= ?", f.PeriodEnd)
	}
	if f.AnnDateBefore != "" {
		q = q.Where("ann_date < ?", f.AnnDateBefore)
	}
	if f.ProgressCode != "" {
		q = q.Where("progress_code = ?", f.ProgressCode)
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
// dictionary for the corporate_action dataset. dataType is the action_type
// (dividend / right_issue).
func (d *CorporateActionDao) ResolveQueryFields(ctx context.Context, source, dataType string, requested []string) ([]ResolvedField, []model.UnknownFieldHint, error) {
	return d.FieldDictDao.ResolveFields(ctx, source, "corporate_action", dataType, requested)
}

// QueryFlat runs a flat query against corporate_action. See
// FinancialStatementDao.QueryFlat for semantics.
func (d *CorporateActionDao) QueryFlat(ctx context.Context, source string, f *model.CorporateActionFilters, resolved []ResolvedField, limit, offset int) ([]map[string]any, error) {
	selectClause, _ := BuildFlatSelect(resolved)
	q := d.db.WithContext(ctx).Table("ods.corporate_action").Where("source = ?", source)
	q = applyCorpActionFilters(q, f)
	q = q.Order("security_id ASC, report_period DESC, ann_date DESC")
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

// QueryNested runs a nested query against corporate_action. See
// FinancialStatementDao.QueryNested for semantics.
func (d *CorporateActionDao) QueryNested(ctx context.Context, source string, f *model.CorporateActionFilters, resolved []ResolvedField, limit, offset int) ([]model.NestedRow, error) {
	topLevel, dataJSONFields := SplitResolved(resolved)

	selectParts := []string{
		"security_id", "source", "action_type", "report_period",
		"ann_date", "progress_code",
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
		Table("corporate_action").
		Select(strings.Join(selectParts, ", ")).
		Where("source = ?", source)
	q = applyCorpActionFilters(q, f)
	q = q.Order("security_id ASC, report_period DESC, ann_date DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}

	type rawNestedRow struct {
		SecurityID   uint64 `gorm:"column:security_id"`
		Source       string `gorm:"column:source"`
		ActionType   string `gorm:"column:action_type"`
		ReportPeriod string `gorm:"column:report_period"`
		AnnDate      string `gorm:"column:ann_date"`
		ProgressCode string `gorm:"column:progress_code"`
		DataJSON     []byte `gorm:"column:data_json"`
	}
	var rawRows []rawNestedRow
	if err := q.Scan(&rawRows).Error; err != nil {
		return nil, err
	}

	rows := make([]model.NestedRow, 0, len(rawRows))
	for _, r := range rawRows {
		row := model.NestedRow{
			TopLevel: map[string]any{
				"security_id":   r.SecurityID,
				"source":        r.Source,
				"action_type":   r.ActionType,
				"report_period": r.ReportPeriod,
				"ann_date":      r.AnnDate,
				"progress_code": r.ProgressCode,
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
