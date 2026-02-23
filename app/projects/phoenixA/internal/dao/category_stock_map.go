package dao

import (
	"context"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type CategoryStockMapDao interface {
	core.Component
	Create(ctx context.Context, m *model.CategoryStockMap) error
	BatchUpsert(ctx context.Context, list []*model.CategoryStockMap, chunkSize int) error
	// ReplaceCategoriesForStocks deletes all existing categories for the given stocks and inserts new ones.
	// Input: map[stock_code] -> list of category_codes
	ReplaceCategoriesForStocks(ctx context.Context, stockToCategories map[string][]string) error
	// ReplaceStocksForCategories deletes all existing stocks for the given categories and inserts new ones.
	// Input: map[category_code] -> list of stock_codes
	ReplaceStocksForCategories(ctx context.Context, categoryToStocks map[string][]string) error
	Delete(ctx context.Context, categoryCode, stockCode string) error
	ListByCategory(ctx context.Context, categoryCode string, limit, offset int) ([]*model.CategoryStockMap, error)
	ListByStock(ctx context.Context, stockCode string) ([]*model.CategoryStockMap, error)
	CountByCategory(ctx context.Context, categoryCode string) (int64, error)
}

type categoryStockMapDaoImpl struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewCategoryStockMapDao(dsName string) CategoryStockMapDao {
	return &categoryStockMapDaoImpl{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_CATEGORY_STOCK_MAP, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

func (d *categoryStockMapDaoImpl) Start(ctx context.Context) error {
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return err
	}
	d.db = db
	return nil
}

func (d *categoryStockMapDaoImpl) Create(ctx context.Context, m *model.CategoryStockMap) error {
	return d.db.WithContext(ctx).Create(m).Error
}

func (d *categoryStockMapDaoImpl) BatchUpsert(ctx context.Context, list []*model.CategoryStockMap, chunkSize int) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "category_code"}, {Name: "stock_code"}},
		DoNothing: true,
	}).CreateInBatches(list, chunkSize).Error
}

func (d *categoryStockMapDaoImpl) ReplaceCategoriesForStocks(ctx context.Context, stockToCategories map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		stocks := make([]string, 0, len(stockToCategories))
		for stock := range stockToCategories {
			stocks = append(stocks, stock)
		}
		if len(stocks) == 0 {
			return nil
		}
		// 1. Delete all categories for these stocks
		if err := tx.Where("stock_code IN ?", stocks).Delete(&model.CategoryStockMap{}).Error; err != nil {
			return err
		}
		// 2. Insert new relations
		var toInsert []*model.CategoryStockMap
		for stock, categories := range stockToCategories {
			for _, cat := range categories {
				toInsert = append(toInsert, &model.CategoryStockMap{
					StockCode:    stock,
					CategoryCode: cat,
				})
			}
		}
		if len(toInsert) > 0 {
			if err := tx.CreateInBatches(toInsert, 500).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

func (d *categoryStockMapDaoImpl) ReplaceStocksForCategories(ctx context.Context, categoryToStocks map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		categories := make([]string, 0, len(categoryToStocks))
		for cat := range categoryToStocks {
			categories = append(categories, cat)
		}
		if len(categories) == 0 {
			return nil
		}
		// 1. Delete all stocks for these categories
		if err := tx.Where("category_code IN ?", categories).Delete(&model.CategoryStockMap{}).Error; err != nil {
			return err
		}
		// 2. Insert new relations
		var toInsert []*model.CategoryStockMap
		for cat, stocks := range categoryToStocks {
			for _, stock := range stocks {
				toInsert = append(toInsert, &model.CategoryStockMap{
					CategoryCode: cat,
					StockCode:    stock,
				})
			}
		}
		if len(toInsert) > 0 {
			if err := tx.CreateInBatches(toInsert, 500).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

func (d *categoryStockMapDaoImpl) Delete(ctx context.Context, categoryCode, stockCode string) error {
	return d.db.WithContext(ctx).Where("category_code = ? AND stock_code = ?", categoryCode, stockCode).Delete(&model.CategoryStockMap{}).Error
}

func (d *categoryStockMapDaoImpl) ListByCategory(ctx context.Context, categoryCode string, limit, offset int) ([]*model.CategoryStockMap, error) {
	var list []*model.CategoryStockMap
	err := d.db.WithContext(ctx).Where("category_code = ?", categoryCode).Limit(limit).Offset(offset).Find(&list).Error
	return list, err
}

func (d *categoryStockMapDaoImpl) ListByStock(ctx context.Context, stockCode string) ([]*model.CategoryStockMap, error) {
	var list []*model.CategoryStockMap
	err := d.db.WithContext(ctx).Where("stock_code = ?", stockCode).Find(&list).Error
	return list, err
}

func (d *categoryStockMapDaoImpl) CountByCategory(ctx context.Context, categoryCode string) (int64, error) {
	var count int64
	err := d.db.WithContext(ctx).Model(&model.CategoryStockMap{}).Where("category_code = ?", categoryCode).Count(&count).Error
	return count, err
}
