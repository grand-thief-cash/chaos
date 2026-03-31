package service

import (
	"context"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type MarketCategoryMairui struct {
	*core.BaseComponent
	Dao *dao.MarketCategoryMairui `infra:"dep:dao_market_category_mairui"`
}

func NewMarketCategoryMairui() *MarketCategoryMairui {
	return &MarketCategoryMairui{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_MARKET_CATEGORY_MAIRUI),
	}
}

func (s *MarketCategoryMairui) Create(ctx context.Context, m *model.CategoryMairui) error {
	return s.Dao.Create(ctx, m)
}

func (s *MarketCategoryMairui) Update(ctx context.Context, m *model.CategoryMairui) error {
	return s.Dao.Update(ctx, m)
}

func (s *MarketCategoryMairui) BatchUpsert(ctx context.Context, list []*model.CategoryMairui) error {
	if len(list) == 0 {
		return nil
	}
	return s.Dao.BatchUpsert(ctx, list, 500)
}

func (s *MarketCategoryMairui) Get(ctx context.Context, code string) (*model.CategoryMairui, error) {
	return s.Dao.Get(ctx, code)
}

func (s *MarketCategoryMairui) Delete(ctx context.Context, code string) error {
	return s.Dao.Delete(ctx, code)
}

func (s *MarketCategoryMairui) List(ctx context.Context, f *model.CategoryFiltersMairui, page, pageSize int) ([]*model.CategoryMairui, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 10
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.List(ctx, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.Count(ctx, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}
