package service

import (
	"context"
	"errors"

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

// Query returns financial statements matching the given filters.
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
