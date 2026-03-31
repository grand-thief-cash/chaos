package service

import (
	"context"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type CategoryStockMapService struct {
	*core.BaseComponent
	Dao dao.CategoryStockMapDao `infra:"dep:dao_category_stock_map"`
}

func NewCategoryStockMapService() *CategoryStockMapService {
	return &CategoryStockMapService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_CATEGORY_STOCK_MAP, consts.COMPONENT_LOGGING),
	}
}

func (s *CategoryStockMapService) Create(ctx context.Context, m *model.CategoryStockMap) error {
	return s.Dao.Create(ctx, m)
}

func (s *CategoryStockMapService) BatchUpsert(ctx context.Context, list []*model.CategoryStockMap) error {
	if len(list) == 0 {
		return nil
	}
	return s.Dao.BatchUpsert(ctx, list, 500)
}

// ReplaceCategoriesForStocks deletes all existing categories for the given stocks and inserts new ones.
// Input: map[stock_code] -> list of category_codes
func (s *CategoryStockMapService) ReplaceCategoriesForStocks(ctx context.Context, stockToCategories map[string][]string) error {
	return s.Dao.ReplaceCategoriesForStocks(ctx, stockToCategories)
}

// ReplaceStocksForCategories deletes all existing stocks for the given categories and inserts new ones.
// Input: map[category_code] -> list of stock_codes
func (s *CategoryStockMapService) ReplaceStocksForCategories(ctx context.Context, categoryToStocks map[string][]string) error {
	return s.Dao.ReplaceStocksForCategories(ctx, categoryToStocks)
}

func (s *CategoryStockMapService) Delete(ctx context.Context, categoryCode, stockCode string) error {
	return s.Dao.Delete(ctx, categoryCode, stockCode)
}

func (s *CategoryStockMapService) ListByCategory(ctx context.Context, categoryCode string, page, pageSize int) ([]*model.CategoryStockMap, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 10
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.ListByCategory(ctx, categoryCode, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.CountByCategory(ctx, categoryCode)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}

func (s *CategoryStockMapService) ListByStock(ctx context.Context, stockCode string) ([]*model.CategoryStockMap, error) {
	return s.Dao.ListByStock(ctx, stockCode)
}
