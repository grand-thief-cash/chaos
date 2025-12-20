package service

import (
	"context"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// StockZhAListService is a thin layer delegating to StockZhAListDao.
// It mirrors cronjob's service style (RunService).
type StockZhAListService struct {
	*core.BaseComponent
	Dao dao.StockZhAListDao `infra:"dep:dao_stock_zh_a_list"`
}

func NewStockZhAListService() *StockZhAListService {
	return &StockZhAListService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_STOCK_ZH_A_LIST)}
}

func (s *StockZhAListService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *StockZhAListService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

func (s *StockZhAListService) Create(ctx context.Context, stock *model.StockZhAList) error {
	return s.Dao.Create(ctx, stock)
}

func (s *StockZhAListService) BatchUpsert(ctx context.Context, list []*model.StockZhAList, chunkSize int) (int64, error) {
	return s.Dao.BatchUpsert(ctx, list, chunkSize)
}

func (s *StockZhAListService) Get(ctx context.Context, code string) (*model.StockZhAList, error) {
	return s.Dao.Get(ctx, code)
}

func (s *StockZhAListService) Update(ctx context.Context, stock *model.StockZhAList) error {
	return s.Dao.Update(ctx, stock)
}

func (s *StockZhAListService) DeleteAll(ctx context.Context) (int64, error) {
	return s.Dao.DeleteAll(ctx)
}

func (s *StockZhAListService) ListFiltered(ctx context.Context, f *model.StockZhAListFilters, limit, offset int) ([]*model.StockZhAList, error) {
	return s.Dao.ListFiltered(ctx, f, limit, offset)
}

func (s *StockZhAListService) CountFiltered(ctx context.Context, f *model.StockZhAListFilters) (int64, error) {
	return s.Dao.CountFiltered(ctx, f)
}
