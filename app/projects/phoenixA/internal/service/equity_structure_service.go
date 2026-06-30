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

type EquityStructureService struct {
	*core.BaseComponent
	Dao *dao.EquityStructureDao `infra:"dep:dao_equity_structure"`
}

func NewEquityStructureService() *EquityStructureService {
	return &EquityStructureService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_EQUITY_STRUCTURE, consts.COMPONENT_LOGGING),
	}
}

func (s *EquityStructureService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_equity_structure is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *EquityStructureService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *EquityStructureService) BatchUpsert(ctx context.Context, list []*model.EquityStructure) error {
	if len(list) == 0 {
		return nil
	}
	logging.Infof(ctx, "EquityStructureService BatchUpsert count=%d", len(list))
	return s.Dao.BatchUpsert(ctx, list)
}

// QueryFlat runs a dictionary-resolved flat query against equity_structure.
func (s *EquityStructureService) QueryFlat(ctx context.Context, source string, f *model.EquityStructureFilters, requestedFields []string, page, pageSize int) (*model.FlatQueryResponse, error) {
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

	// equity_structure has a single data_type — pass "" so the resolver
	// matches fields with data_type IS NULL or data_type = 'equity_structure'.
	resolved, unknown, err := s.Dao.ResolveQueryFields(ctx, source, "", requestedFields)
	if err != nil {
		return nil, err
	}
	if len(unknown) > 0 {
		return nil, &model.FieldResolutionError{
			Code:    "unknown_field",
			Dataset: "equity_structure",
			Source:  source,
			Unknown: unknown,
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
		Dataset:     "equity_structure",
		Source:      source,
		Rows:        flatRowsFromMaps(rows),
		Fields:      fieldMetasFromResolved(resolved),
		Total:       count,
		Page:        page,
		PageSize:    pageSize,
	}, nil
}

// QueryNested runs a dictionary-resolved nested query against equity_structure.
func (s *EquityStructureService) QueryNested(ctx context.Context, source string, f *model.EquityStructureFilters, requestedFields []string, page, pageSize int) (*model.NestedQueryResponse, error) {
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

	resolved, unknown, err := s.Dao.ResolveQueryFields(ctx, source, "", requestedFields)
	if err != nil {
		return nil, err
	}
	if len(unknown) > 0 {
		return nil, &model.FieldResolutionError{
			Code:    "unknown_field",
			Dataset: "equity_structure",
			Source:  source,
			Unknown: unknown,
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
		Dataset:     "equity_structure",
		Source:      source,
		Rows:        rows,
		Total:       count,
		Page:        page,
		PageSize:    pageSize,
	}, nil
}
