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

// BarsService handles business logic for unified bars data.
type BarsService struct {
	*core.BaseComponent
	Dao *dao.BarsDao `infra:"dep:dao_bars"`
}

func NewBarsService() *BarsService {
	return &BarsService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_BARS, consts.COMPONENT_LOGGING),
	}
}

func (s *BarsService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_bars is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *BarsService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

// BatchUpsert writes standard bars.
func (s *BarsService) BatchUpsert(ctx context.Context, q *model.BarsQuery, barsJSON json.RawMessage) error {
	var bars []*model.StandardBar
	if err := json.Unmarshal(barsJSON, &bars); err != nil {
		return err
	}
	logging.Infof(ctx, "BarsService BatchUpsert %d bars for %s/%s/%s/%s",
		len(bars), q.AssetType, q.Market, q.Period, q.Adjust)
	return s.Dao.BatchUpsert(ctx, q, bars)
}

// BatchUpsertExt writes source-specific extension bars.
func (s *BarsService) BatchUpsertExt(ctx context.Context, source string, q *model.BarsQuery, extJSON json.RawMessage) error {
	var ext []*model.BarsExtBaostock
	if err := json.Unmarshal(extJSON, &ext); err != nil {
		return err
	}
	logging.Infof(ctx, "BarsService BatchUpsertExt %d ext rows from %s", len(ext), source)
	return s.Dao.BatchUpsertExt(ctx, source, q, ext)
}

// GetLatestUpdateBySymbols returns map[symbol]lastTradeDate.
func (s *BarsService) GetLatestUpdateBySymbols(ctx context.Context, q *model.BarsQuery) (map[string]string, error) {
	if len(q.Symbols) == 0 {
		return map[string]string{}, nil
	}
	return s.Dao.GetLatestUpdateBySymbols(ctx, q)
}

// QueryBars returns standard bars for a single symbol.
func (s *BarsService) QueryBars(ctx context.Context, q *model.BarsQuery) ([]*model.StandardBar, error) {
	return s.Dao.QueryBars(ctx, q)
}
