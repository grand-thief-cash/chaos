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

type MarketObservationService struct {
	*core.BaseComponent
	Dao     *dao.MarketObservationDao `infra:"dep:dao_market_observation"`
	Resolve *ResolveCache             `infra:"dep:svc_resolve_cache"`
}

func NewMarketObservationService() *MarketObservationService {
	return &MarketObservationService{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_SVC_MARKET_OBSERVATION,
			consts.COMPONENT_LOGGING,
		),
	}
}

func (s *MarketObservationService) Start(ctx context.Context) error {
	if s.Dao == nil || s.Resolve == nil {
		return errors.New("market observation dependencies are nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *MarketObservationService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

func (s *MarketObservationService) BatchUpsert(
	ctx context.Context, rows []*model.MarketObservationDaily,
) error {
	securityIDs := make([]uint64, 0, len(rows))
	for _, row := range rows {
		if row == nil || row.SecurityID == 0 || row.TradeDate == "" ||
			row.ObservationType == "" || row.Source == "" || row.Unit == "" {
			return NewValidationError(
				"security_id, trade_date, observation_type, source and unit are required",
			)
		}
		securityIDs = append(securityIDs, row.SecurityID)
	}
	if err := s.Resolve.ValidateSecurityIDsExist(ctx, securityIDs); err != nil {
		return err
	}
	return s.Dao.BatchUpsert(ctx, rows)
}

func (s *MarketObservationService) Query(
	ctx context.Context,
	source string,
	f *model.MarketObservationFilters,
	limit, offset int,
) ([]*model.MarketObservationDaily, error) {
	if source == "" {
		return nil, NewValidationError("source is required")
	}
	return s.Dao.Query(
		ctx,
		source,
		f,
		dailyDataQueryLimit(limit),
		offset,
	)
}

func (s *MarketObservationService) LastDates(
	ctx context.Context,
	source string,
	securityIDs []uint64,
) (map[uint64]string, error) {
	if source == "" || len(securityIDs) == 0 {
		return nil, NewValidationError("source and security_ids are required")
	}
	return s.Dao.LastDates(ctx, source, securityIDs)
}
