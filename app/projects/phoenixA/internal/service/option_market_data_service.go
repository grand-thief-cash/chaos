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

type OptionMarketDataService struct {
	*core.BaseComponent
	Dao *dao.OptionMarketDataDao `infra:"dep:dao_option_market_data"`
}

func NewOptionMarketDataService() *OptionMarketDataService {
	return &OptionMarketDataService{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_SVC_OPTION_MARKET_DATA,
			consts.COMPONENT_LOGGING,
		),
	}
}

func (s *OptionMarketDataService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("option market data DAO is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *OptionMarketDataService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

func (s *OptionMarketDataService) BatchUpsertOptionQVIX(
	ctx context.Context, rows []*model.OptionQVIXDaily,
) error {
	for _, row := range rows {
		if row == nil || row.Symbol == "" || row.TradeDate == "" ||
			row.Open == nil || row.High == nil || row.Low == nil || row.Close == nil {
			return NewValidationError("symbol, trade_date and OHLC are required")
		}
	}
	return s.Dao.BatchUpsertOptionQVIX(ctx, rows)
}

func (s *OptionMarketDataService) BatchUpsertOptionDailyStats(
	ctx context.Context, rows []*model.OptionDailyStats,
) error {
	for _, row := range rows {
		if row == nil || row.Exchange == "" || row.UnderlyingSymbol == "" ||
			row.TradeDate == "" {
			return NewValidationError(
				"exchange, underlying_symbol and trade_date are required",
			)
		}
	}
	return s.Dao.BatchUpsertOptionDailyStats(ctx, rows)
}

func (s *OptionMarketDataService) QueryOptionQVIX(
	ctx context.Context, f *model.OptionMarketDataFilters, limit, offset int,
) ([]*model.OptionQVIXDaily, error) {
	return s.Dao.QueryOptionQVIX(
		ctx,
		f,
		dailyDataQueryLimit(limit),
		offset,
	)
}

func (s *OptionMarketDataService) QueryOptionDailyStats(
	ctx context.Context, f *model.OptionMarketDataFilters, limit, offset int,
) ([]*model.OptionDailyStats, error) {
	return s.Dao.QueryOptionDailyStats(
		ctx,
		f,
		dailyDataQueryLimit(limit),
		offset,
	)
}

func (s *OptionMarketDataService) LastOptionQVIXDates(
	ctx context.Context, symbols []string,
) (map[string]string, error) {
	return s.Dao.LastOptionQVIXDates(ctx, symbols)
}

func (s *OptionMarketDataService) LastOptionDailyStatsDates(
	ctx context.Context, exchanges []string,
) (map[string]string, error) {
	return s.Dao.LastOptionDailyStatsDates(ctx, exchanges)
}
