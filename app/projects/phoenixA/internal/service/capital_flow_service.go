package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type CapitalFlowService struct {
	*core.BaseComponent
	Dao *dao.CapitalFlowDao `infra:"dep:dao_capital_flow"`
}

func NewCapitalFlowService() *CapitalFlowService {
	return &CapitalFlowService{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_SVC_CAPITAL_FLOW,
			consts.COMPONENT_LOGGING,
		),
	}
}

func (s *CapitalFlowService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("capital flow DAO is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *CapitalFlowService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

func (s *CapitalFlowService) BatchUpsertMarginSummary(
	ctx context.Context, rows []*model.MarginSummaryDaily,
) error {
	for _, row := range rows {
		if row == nil || row.TradeDate == "" {
			return NewValidationError("trade_date is required")
		}
	}
	return s.Dao.BatchUpsertMarginSummary(ctx, rows)
}

func (s *CapitalFlowService) BatchUpsertHSGT(
	ctx context.Context, rows []*model.HSGTDaily,
) error {
	for _, row := range rows {
		if row == nil || row.Symbol == "" || row.TradeDate == "" {
			return NewValidationError("symbol and trade_date are required")
		}
	}
	return s.Dao.BatchUpsertHSGT(ctx, rows)
}

func (s *CapitalFlowService) QueryMarginSummary(
	ctx context.Context, f *model.CapitalFlowFilters, limit, offset int,
) ([]*model.MarginSummaryDaily, error) {
	return s.Dao.QueryMarginSummary(
		ctx,
		f,
		dailyDataQueryLimit(limit),
		offset,
	)
}

func (s *CapitalFlowService) QueryHSGT(
	ctx context.Context, f *model.CapitalFlowFilters, limit, offset int,
) ([]*model.HSGTDaily, error) {
	return s.Dao.QueryHSGT(ctx, f, dailyDataQueryLimit(limit), offset)
}

func (s *CapitalFlowService) LastMarginSummaryDate(
	ctx context.Context,
) (string, error) {
	return s.Dao.LastMarginSummaryDate(ctx)
}

func (s *CapitalFlowService) LastHSGTDates(
	ctx context.Context, symbols []string,
) (map[string]string, error) {
	return s.Dao.LastHSGTDates(ctx, symbols)
}
