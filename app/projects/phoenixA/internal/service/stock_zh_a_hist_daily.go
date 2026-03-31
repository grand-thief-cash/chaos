package service

import (
	"context"
	"encoding/json"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type StockZhAHistDailyService struct {
	*core.BaseComponent
	Dao *dao.StockZhAHistDaily `infra:"dep:dao_stock_zh_a_hist_daily"`
}

func NewStockZhAHistDailyService() *StockZhAHistDailyService {
	return &StockZhAHistDailyService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_STOCK_ZH_A_HIST_DAILY, consts.COMPONENT_LOGGING),
	}
}

func (s *StockZhAHistDailyService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("the dao dao_stock_zh_a_hist_daily is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *StockZhAHistDailyService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

// BatchUpsert handles the logic for saving stock history data.
func (s *StockZhAHistDailyService) BatchUpsert(ctx context.Context, reqMeta *model.HistDataRequestMeta, dataJSON json.RawMessage) error {

	var list []*model.StockZhAHistDaily
	if err := json.Unmarshal(dataJSON, &list); err != nil {
		return err
	}
	logging.Infof(ctx, "StockZhAHistDailyService Batch save %d daily records", len(list))
	return s.Dao.BatchUpsert(ctx, reqMeta, list)
}

// GetLatestUpdateByCodes retrieves the last update date for all stocks in the given table.
func (s *StockZhAHistDailyService) GetLatestUpdateByCodes(ctx context.Context, req *model.HistDataRequestMeta) (map[string]string, error) {

	if len(req.Codes) == 0 {
		return map[string]string{}, nil
	}

	res, err := s.Dao.GetLatestUpdateByCodes(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "Failed to get latest update by codes: %v", err)
		return map[string]string{}, err
	}

	return res, nil
}

// GetStockHist returns daily history for a code within [startDate, endDate].
func (s *StockZhAHistDailyService) GetStockHist(ctx context.Context, req *model.HistDataRequestMeta) ([]*model.StockZhAHistDaily, error) {

	//logging.Infof(ctx, "Query daily hist code=%s range=%s..%s limit=%d offset=%d fields=%v", code, startDate, endDate, limit, offset, fields)
	return s.Dao.GetStockHist(ctx, req)
}
