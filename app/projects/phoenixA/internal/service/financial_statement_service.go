package service

import (
	"context"
	"errors"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// FinancialStatementService handles business logic for financial statement data.
type FinancialStatementService struct {
	*core.BaseComponent
	Dao *dao.FinancialStatementDao `infra:"dep:dao_financial_stmt"`
}

func NewFinancialStatementService() *FinancialStatementService {
	return &FinancialStatementService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_FINANCIAL_STMT, consts.COMPONENT_LOGGING),
	}
}

func (s *FinancialStatementService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_financial_stmt is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *FinancialStatementService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

// BatchUpsert upserts financial statements.
func (s *FinancialStatementService) BatchUpsert(ctx context.Context, list []*model.FinancialStatement) error {
	if len(list) == 0 {
		return nil
	}
	logging.Infof(ctx, "FinancialStatementService BatchUpsert count=%d", len(list))
	return s.Dao.BatchUpsert(ctx, list)
}

// Query returns financial statements matching the given filters (legacy path,
// returns full structs). Kept for backward compatibility; new callers should
// use QueryFlat / QueryNested which go through the field dictionary.
func (s *FinancialStatementService) Query(ctx context.Context, source string, f *model.FinancialStatementFilters, page, pageSize int) ([]*model.FinancialStatement, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	if pageSize > 1000 {
		pageSize = 1000
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.Query(ctx, source, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.Count(ctx, source, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}

// QueryFlat runs a dictionary-resolved flat query. requestedFields may use
// raw_field (e.g. TOTAL_ASSETS) or canonical_field (e.g. total_assets) names.
// When the field list is empty, all top-level columns are returned. Returns
// a *model.FieldResolutionError when any requested field cannot be resolved.
func (s *FinancialStatementService) QueryFlat(ctx context.Context, source string, f *model.FinancialStatementFilters, requestedFields []string, page, pageSize int) (*model.FlatQueryResponse, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	if pageSize > 1000 {
		pageSize = 1000
	}
	offset := (page - 1) * pageSize

	dataType := ""
	if f != nil {
		dataType = f.StatementType
	}
	resolved, unknown, err := s.Dao.ResolveQueryFields(ctx, source, dataType, requestedFields)
	if err != nil {
		return nil, err
	}
	if len(unknown) > 0 {
		return nil, &model.FieldResolutionError{
			Code:     "unknown_field",
			Dataset:  "financial_statement",
			DataType: dataType,
			Source:   source,
			Unknown:  unknown,
		}
	}

	rows, err := s.Dao.QueryFlat(ctx, source, f, resolved, pageSize, offset)
	if err != nil {
		return nil, err
	}
	count, err := s.Dao.Count(ctx, source, f)
	if err != nil {
		return nil, err
	}

	return &model.FlatQueryResponse{
		GeneratedAt: time.Now(),
		Dataset:     "financial_statement",
		Source:      source,
		DataType:    dataType,
		Rows:        flatRowsFromMaps(rows),
		Fields:      fieldMetasFromResolved(resolved),
		Total:       count,
		Page:        page,
		PageSize:    pageSize,
	}, nil
}

// QueryNested runs a dictionary-resolved nested query. Top-level columns go
// into TopLevel; data_json (full when no fields requested, filtered otherwise)
// goes into DataJSON.
func (s *FinancialStatementService) QueryNested(ctx context.Context, source string, f *model.FinancialStatementFilters, requestedFields []string, page, pageSize int) (*model.NestedQueryResponse, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	if pageSize > 1000 {
		pageSize = 1000
	}
	offset := (page - 1) * pageSize

	dataType := ""
	if f != nil {
		dataType = f.StatementType
	}
	resolved, unknown, err := s.Dao.ResolveQueryFields(ctx, source, dataType, requestedFields)
	if err != nil {
		return nil, err
	}
	if len(unknown) > 0 {
		return nil, &model.FieldResolutionError{
			Code:     "unknown_field",
			Dataset:  "financial_statement",
			DataType: dataType,
			Source:   source,
			Unknown:  unknown,
		}
	}

	rows, err := s.Dao.QueryNested(ctx, source, f, resolved, pageSize, offset)
	if err != nil {
		return nil, err
	}
	count, err := s.Dao.Count(ctx, source, f)
	if err != nil {
		return nil, err
	}

	return &model.NestedQueryResponse{
		GeneratedAt: time.Now(),
		Dataset:     "financial_statement",
		Source:      source,
		DataType:    dataType,
		Rows:        rows,
		Total:       count,
		Page:        page,
		PageSize:    pageSize,
	}, nil
}

// flatRowsFromMaps converts []map[string]any (gorm Scan target) into
// []FlatRow, parsing numeric strings back into float64 where the dictionary
// said value_type was number/integer. gorm+pgx returns JSONB numeric values
// as float64 already when scanned into any; text-cast expressions return
// string, so we leave those as-is.
func flatRowsFromMaps(rows []map[string]any) []model.FlatRow {
	out := make([]model.FlatRow, 0, len(rows))
	for _, r := range rows {
		out = append(out, model.FlatRow(r))
	}
	return out
}

// fieldMetasFromResolved projects resolved fields into the FieldMeta list
// attached to flat responses.
func fieldMetasFromResolved(resolved []dao.ResolvedField) []model.FieldMeta {
	if len(resolved) == 0 {
		return nil
	}
	out := make([]model.FieldMeta, 0, len(resolved))
	for _, r := range resolved {
		out = append(out, model.FieldMeta{
			Name:            r.OutputKey,
			RawField:        r.RawField,
			CanonicalField:  r.CanonicalField,
			LabelZh:         r.LabelZh,
			ValueType:       r.ValueType,
			Unit:            r.Unit,
			Scale:           r.Scale,
			StorageLocation: r.StorageLocation,
			IsMetadata:      r.IsMetadata,
			IsCore:          r.IsCore,
		})
	}
	return out
}
