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

// BarsService handles business logic for unified bars data.
//
// The controller validates security_id against security_registry and the DAO
// keeps the same identity in physical storage.
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

// BatchUpsert writes security_id-keyed standard bars.
func (s *BarsService) BatchUpsert(ctx context.Context, q *model.BarsQuery, bars []*model.StandardBar) error {
	logging.Infof(ctx, "BarsService BatchUpsert %d bars for %s/%s/%s/%s",
		len(bars), q.AssetType, q.Market, q.Period, q.Adjust)
	return s.Dao.BatchUpsert(ctx, q, bars)
}

// BatchUpsertExt writes an optional extension schema; it does not create a
// second source version of the canonical bar.
func (s *BarsService) BatchUpsertExt(ctx context.Context, extensionKind string, q *model.BarsQuery, ext []*model.BarsExtBaostock) error {
	logging.Infof(ctx, "BarsService BatchUpsertExt %d ext rows kind=%s", len(ext), extensionKind)
	return s.Dao.BatchUpsertExt(ctx, extensionKind, q, ext)
}

// GetLatestUpdateBySecurityIDs returns map[security_id]lastTradeDate.
func (s *BarsService) GetLatestUpdateBySecurityIDs(ctx context.Context, q *model.BarsQuery) (map[uint64]string, error) {
	if len(q.SecurityIDs) == 0 {
		return map[uint64]string{}, nil
	}
	return s.Dao.GetLatestUpdateBySecurityIDs(ctx, q)
}

// QueryBars returns standard bars for a single security.
func (s *BarsService) QueryBars(ctx context.Context, q *model.BarsQuery) ([]*model.StandardBar, error) {
	return s.Dao.QueryBars(ctx, q)
}
