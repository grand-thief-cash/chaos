package service

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type StockZhAHistService struct {
	*core.BaseComponent
	Dao dao.StockZhAHistDao `infra:"dep:dao_stock_zh_a_hist"`
}

func NewStockZhAHistService() *StockZhAHistService {
	return &StockZhAHistService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_STOCK_ZH_A_HIST, consts.COMPONENT_LOGGING),
	}
}

func (s *StockZhAHistService) Start(ctx context.Context) error {
	return s.BaseComponent.Start(ctx)
}

func (s *StockZhAHistService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

// BatchSaveStockData handles the logic for saving stock history data.
func (s *StockZhAHistService) BatchSaveStockData(ctx context.Context, frequency, adjust string, dataJSON json.RawMessage) error {
	if frequency == "" || adjust == "" {
		return fmt.Errorf("missing frequency or adjust")
	}

	frequency = strings.ToLower(frequency)

	// Temporary Check: Only support daily
	if frequency != "d" && frequency != "daily" {
		logging.Infof(ctx, "Skipping non-daily data save for frequency: %s", frequency)
		return nil
	}

	var list []*model.StockZhAHistDaily
	if err := json.Unmarshal(dataJSON, &list); err != nil {
		return err
	}

	logging.Infof(ctx, "StockZhAHistService Batch save %d daily records", len(list))
	return s.Dao.BatchSaveDaily(ctx, frequency, adjust, list)
}

// GetStockLastUpdates retrieves the last update date for all stocks in the given table.
func (s *StockZhAHistService) GetStockLastUpdates(ctx context.Context, frequency, adjust string, codes []string) (map[string]string, error) {
	if frequency == "" || adjust == "" {
		return nil, fmt.Errorf("missing frequency or adjust")
	}
	frequency = strings.ToLower(frequency)

	if len(codes) == 0 {
		return s.Dao.GetLatestDateBatch(ctx, frequency, adjust)
	}

	return s.Dao.GetLatestDateByCodes(ctx, frequency, adjust, codes)
}

// GetStockHist returns daily history for a code within [startDate, endDate].
func (s *StockZhAHistService) GetStockHist(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int) ([]*model.StockZhAHistDaily, error) {
	return s.GetStockHistSelected(ctx, frequency, adjust, code, startDate, endDate, limit, offset, nil)
}

// GetStockHistSelected returns daily history for a code within [startDate, endDate], selecting only requested fields.
// fields are JSON field names (e.g. open, close). date will be auto-included.
func (s *StockZhAHistService) GetStockHistSelected(ctx context.Context, frequency, adjust, code, startDate, endDate string, limit, offset int, fields []string) ([]*model.StockZhAHistDaily, error) {
	if code == "" || startDate == "" || endDate == "" {
		return nil, fmt.Errorf("missing code or start_date or end_date")
	}

	frequency = strings.ToLower(strings.TrimSpace(frequency))
	if frequency == "" {
		frequency = "daily"
	}
	adjust = strings.ToLower(strings.TrimSpace(adjust))
	if adjust == "" {
		adjust = "nf"
	}

	// Current models/dao query is implemented for daily only.
	if frequency != "d" && frequency != "daily" {
		return nil, fmt.Errorf("only daily frequency is supported")
	}

	if startDate > endDate {
		return nil, fmt.Errorf("start_date must be <= end_date")
	}

	if limit < 0 {
		limit = 0
	}
	if offset < 0 {
		offset = 0
	}
	const maxLimit = 5000
	if limit == 0 {
		limit = 1000
	}
	if limit > maxLimit {
		limit = maxLimit
	}

	logging.Infof(ctx, "Query daily hist code=%s range=%s..%s limit=%d offset=%d fields=%v", code, startDate, endDate, limit, offset, fields)
	return s.Dao.GetStockHistSelected(ctx, frequency, adjust, code, startDate, endDate, limit, offset, fields)
}
