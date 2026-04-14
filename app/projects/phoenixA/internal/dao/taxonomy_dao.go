package dao

import (
	"context"
	"fmt"
	"strings"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// TaxonomyDao is the unified DAO for taxonomy categories and security mappings.
type TaxonomyDao struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewTaxonomyDao(dsName string) *TaxonomyDao {
	return &TaxonomyDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_TAXONOMY),
		dsName:        dsName,
	}
}

func (d *TaxonomyDao) Start(ctx context.Context) error {
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return fmt.Errorf("get gorm db %s failed: %w", d.dsName, err)
	}
	d.db = db
	return nil
}

func (d *TaxonomyDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsertCategories upserts taxonomy categories for a given source.
func (d *TaxonomyDao) BatchUpsertCategories(ctx context.Context, source string, list []*model.TaxonomyCategory) error {
	if len(list) == 0 {
		return nil
	}
	for _, c := range list {
		c.Source = source
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "source"}, {Name: "code"}},
			DoUpdates: clause.AssignmentColumns([]string{"name", "parent_code", "level", "is_leaf", "attrs_json", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListCategories queries taxonomy categories for a given source with optional filters.
func (d *TaxonomyDao) ListCategories(ctx context.Context, source string, f *model.TaxonomyCategoryFilters, limit, offset int) ([]*model.TaxonomyCategory, error) {
	var list []*model.TaxonomyCategory
	q := d.db.WithContext(ctx).Model(&model.TaxonomyCategory{}).
		Where("source = ?", source).
		Order("code ASC")

	if f != nil {
		if f.ParentCode != nil {
			q = q.Where("parent_code = ?", *f.ParentCode)
		}
		if f.Level != nil {
			q = q.Where("level = ?", *f.Level)
		}
		if f.IsLeaf != nil {
			q = q.Where("is_leaf = ?", *f.IsLeaf)
		}
		if f.Name != "" {
			q = q.Where("name LIKE ?", "%"+strings.TrimSpace(f.Name)+"%")
		}
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

// CountCategories counts taxonomy categories for a given source.
func (d *TaxonomyDao) CountCategories(ctx context.Context, source string, f *model.TaxonomyCategoryFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.TaxonomyCategory{}).Where("source = ?", source)
	if f != nil {
		if f.ParentCode != nil {
			q = q.Where("parent_code = ?", *f.ParentCode)
		}
		if f.Level != nil {
			q = q.Where("level = ?", *f.Level)
		}
		if f.IsLeaf != nil {
			q = q.Where("is_leaf = ?", *f.IsLeaf)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}

// GetCategory retrieves a single taxonomy category by source + code.
func (d *TaxonomyDao) GetCategory(ctx context.Context, source, code string) (*model.TaxonomyCategory, error) {
	var c model.TaxonomyCategory
	err := d.db.WithContext(ctx).Where("source = ? AND code = ?", source, code).First(&c).Error
	if err != nil {
		return nil, err
	}
	return &c, nil
}

// DeleteCategory deletes a single taxonomy category by source + code.
func (d *TaxonomyDao) DeleteCategory(ctx context.Context, source, code string) error {
	return d.db.WithContext(ctx).Where("source = ? AND code = ?", source, code).Delete(&model.TaxonomyCategory{}).Error
}

// BatchUpsertMappings upserts taxonomy-security mappings for a given source.
func (d *TaxonomyDao) BatchUpsertMappings(ctx context.Context, source string, list []*model.TaxonomySecurityMap) error {
	if len(list) == 0 {
		return nil
	}
	for _, m := range list {
		m.Source = source
		if m.AssetType == "" {
			m.AssetType = bizConsts.ASSET_TYPE_STOCK
		}
		if m.Market == "" {
			m.Market = bizConsts.MARKET_ZH_A
		}
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{DoNothing: true}).
		CreateInBatches(list, 500).Error
}

// ReplaceStocksForCategories replaces all symbols for given categories under a source.
func (d *TaxonomyDao) ReplaceStocksForCategories(ctx context.Context, source string, categoryToSymbols map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		categories := make([]string, 0, len(categoryToSymbols))
		for cat := range categoryToSymbols {
			categories = append(categories, cat)
		}
		if len(categories) == 0 {
			return nil
		}
		if err := tx.Where("source = ? AND category_code IN ?", source, categories).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for cat, symbols := range categoryToSymbols {
			for _, sym := range symbols {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					Source:       source,
					CategoryCode: cat,
					Symbol:       sym,
					AssetType:    bizConsts.ASSET_TYPE_STOCK,
					Market:       bizConsts.MARKET_ZH_A,
				})
			}
		}
		if len(toInsert) > 0 {
			return tx.CreateInBatches(toInsert, 500).Error
		}
		return nil
	})
}

// ReplaceCategoriesForSymbols replaces all categories for given symbols under a source.
func (d *TaxonomyDao) ReplaceCategoriesForSymbols(ctx context.Context, source string, symbolToCategories map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		symbols := make([]string, 0, len(symbolToCategories))
		for sym := range symbolToCategories {
			symbols = append(symbols, sym)
		}
		if len(symbols) == 0 {
			return nil
		}
		if err := tx.Where("source = ? AND symbol IN ?", source, symbols).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for sym, cats := range symbolToCategories {
			for _, cat := range cats {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					Source:       source,
					CategoryCode: cat,
					Symbol:       sym,
					AssetType:    bizConsts.ASSET_TYPE_STOCK,
					Market:       bizConsts.MARKET_ZH_A,
				})
			}
		}
		if len(toInsert) > 0 {
			return tx.CreateInBatches(toInsert, 500).Error
		}
		return nil
	})
}

// ListMappingsByCategory returns all security mappings for a given source + category.
func (d *TaxonomyDao) ListMappingsByCategory(ctx context.Context, source, categoryCode string, limit, offset int) ([]*model.TaxonomySecurityMap, error) {
	var list []*model.TaxonomySecurityMap
	q := d.db.WithContext(ctx).Where("source = ? AND category_code = ?", source, categoryCode)
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	err := q.Find(&list).Error
	return list, err
}

// ListMappingsBySymbol returns all taxonomy mappings for a given symbol.
func (d *TaxonomyDao) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMap, error) {
	var list []*model.TaxonomySecurityMap
	err := d.db.WithContext(ctx).Where("symbol = ?", symbol).Find(&list).Error
	return list, err
}

// DeleteMapping deletes a single mapping.
func (d *TaxonomyDao) DeleteMapping(ctx context.Context, source, categoryCode, symbol string) error {
	return d.db.WithContext(ctx).
		Where("source = ? AND category_code = ? AND symbol = ?", source, categoryCode, symbol).
		Delete(&model.TaxonomySecurityMap{}).Error
}
