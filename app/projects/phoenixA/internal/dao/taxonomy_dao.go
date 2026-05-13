package dao

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// TaxonomyDao is the unified DAO for taxonomy categories and security mappings.
type TaxonomyDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
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

// ──────────── Categories ────────────

// BatchUpsertCategories upserts taxonomy categories for a given source + taxonomy + market.
func (d *TaxonomyDao) BatchUpsertCategories(ctx context.Context, source, taxonomy, market string, list []*model.TaxonomyCategory) error {
	if len(list) == 0 {
		return nil
	}
	for _, c := range list {
		c.Source = source
		c.Taxonomy = taxonomy
		if market != "" {
			c.Market = market
		}
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "market"}, {Name: "code"}},
			DoUpdates: clause.AssignmentColumns([]string{"name", "parent_code", "index_code", "level", "is_leaf", "attrs_json", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListCategories queries taxonomy categories with optional filters.
func (d *TaxonomyDao) ListCategories(ctx context.Context, source, taxonomy, market string, f *model.TaxonomyCategoryFilters, limit, offset int) ([]*model.TaxonomyCategory, error) {
	var list []*model.TaxonomyCategory
	q := d.db.WithContext(ctx).Model(&model.TaxonomyCategory{}).
		Where("source = ? AND taxonomy = ?", source, taxonomy).
		Order("code ASC")

	if market != "" {
		q = q.Where("market = ?", market)
	}
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
		// PostgreSQL JSONB containment: attrs_json @> '{"is_pub": 1}'
		if len(f.AttrsContains) > 0 {
			jsonBytes, err := json.Marshal(f.AttrsContains)
			if err == nil {
				q = q.Where("attrs_json @> ?::jsonb", string(jsonBytes))
			}
		}
		// PostgreSQL JSONB key existence: attrs_json ? 'change_reason'
		if f.AttrsHasKey != "" {
			q = q.Where("attrs_json ?? ?", f.AttrsHasKey)
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

// CountCategories counts taxonomy categories.
func (d *TaxonomyDao) CountCategories(ctx context.Context, source, taxonomy, market string, f *model.TaxonomyCategoryFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.TaxonomyCategory{}).
		Where("source = ? AND taxonomy = ?", source, taxonomy)
	if market != "" {
		q = q.Where("market = ?", market)
	}
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
		if len(f.AttrsContains) > 0 {
			jsonBytes, err := json.Marshal(f.AttrsContains)
			if err == nil {
				q = q.Where("attrs_json @> ?::jsonb", string(jsonBytes))
			}
		}
		if f.AttrsHasKey != "" {
			q = q.Where("attrs_json ?? ?", f.AttrsHasKey)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}

// GetCategory retrieves a single taxonomy category.
func (d *TaxonomyDao) GetCategory(ctx context.Context, source, taxonomy, market, code string) (*model.TaxonomyCategory, error) {
	var c model.TaxonomyCategory
	err := d.db.WithContext(ctx).
		Where("source = ? AND taxonomy = ? AND market = ? AND code = ?", source, taxonomy, market, code).
		First(&c).Error
	if err != nil {
		return nil, err
	}
	return &c, nil
}

// DeleteCategory deletes a single taxonomy category.
func (d *TaxonomyDao) DeleteCategory(ctx context.Context, source, taxonomy, market, code string) error {
	return d.db.WithContext(ctx).
		Where("source = ? AND taxonomy = ? AND market = ? AND code = ?", source, taxonomy, market, code).
		Delete(&model.TaxonomyCategory{}).Error
}

// ──────────── Security Mappings ────────────

// SyncMappingsFromConstituents derives category→symbol mappings from industry_constituent + taxonomy_category.
// For each (source, taxonomy, market), it JOINs industry_constituent with taxonomy_category on index_code
// and inserts into taxonomy_security_map.
func (d *TaxonomyDao) SyncMappingsFromConstituents(ctx context.Context, source, taxonomy, market string) (int64, error) {
	sql := `
		INSERT INTO taxonomy_security_map (source, taxonomy, category_code, symbol, asset_type, market)
		SELECT DISTINCT ic.source, ic.taxonomy, tc.code, ic.symbol, 'stock', ic.market
		FROM industry_constituent ic
		JOIN taxonomy_category tc
		  ON tc.index_code = ic.index_code
		 AND tc.source = ic.source
		 AND tc.taxonomy = ic.taxonomy
		 AND tc.market  = ic.market
		WHERE ic.source   = ?
		  AND ic.taxonomy = ?
		  AND ic.market   = ?
		ON CONFLICT (source, taxonomy, category_code, symbol, asset_type, market) DO NOTHING
	`
	result := d.db.WithContext(ctx).Exec(sql, source, taxonomy, market)
	if result.Error != nil {
		return 0, result.Error
	}
	return result.RowsAffected, nil
}

// BatchUpsertMappings upserts taxonomy-security mappings.
func (d *TaxonomyDao) BatchUpsertMappings(ctx context.Context, source, taxonomy string, list []*model.TaxonomySecurityMap) error {
	if len(list) == 0 {
		return nil
	}
	for _, m := range list {
		m.Source = source
		m.Taxonomy = taxonomy
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

// ReplaceStocksForCategories replaces all symbols for given categories.
func (d *TaxonomyDao) ReplaceStocksForCategories(ctx context.Context, source, taxonomy string, categoryToSymbols map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		categories := make([]string, 0, len(categoryToSymbols))
		for cat := range categoryToSymbols {
			categories = append(categories, cat)
		}
		if len(categories) == 0 {
			return nil
		}
		if err := tx.Where("source = ? AND taxonomy = ? AND category_code IN ?", source, taxonomy, categories).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for cat, symbols := range categoryToSymbols {
			for _, sym := range symbols {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					Source:       source,
					Taxonomy:     taxonomy,
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

// ReplaceCategoriesForSymbols replaces all categories for given symbols.
func (d *TaxonomyDao) ReplaceCategoriesForSymbols(ctx context.Context, source, taxonomy string, symbolToCategories map[string][]string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		symbols := make([]string, 0, len(symbolToCategories))
		for sym := range symbolToCategories {
			symbols = append(symbols, sym)
		}
		if len(symbols) == 0 {
			return nil
		}
		if err := tx.Where("source = ? AND taxonomy = ? AND symbol IN ?", source, taxonomy, symbols).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for sym, cats := range symbolToCategories {
			for _, cat := range cats {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					Source:       source,
					Taxonomy:     taxonomy,
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

// ListMappingsByCategory returns all security mappings for a source + taxonomy + category.
func (d *TaxonomyDao) ListMappingsByCategory(ctx context.Context, source, taxonomy, categoryCode string, limit, offset int) ([]*model.TaxonomySecurityMap, error) {
	var list []*model.TaxonomySecurityMap
	q := d.db.WithContext(ctx).Where("source = ? AND taxonomy = ? AND category_code = ?", source, taxonomy, categoryCode)
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
// Performs two queries: first fetches mappings, then fetches category details.
func (d *TaxonomyDao) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMapWithDetail, error) {
	var list []*model.TaxonomySecurityMapWithDetail

	// Query 1: Fetch all mappings for symbol
	type MappingQuery struct {
		Source       string
		Taxonomy     string
		CategoryCode string
		Symbol       string
		AssetType    string
		Market       string
	}
	var mappings []MappingQuery
	err := d.db.WithContext(ctx).
		Table("taxonomy_security_map").
		Where("symbol = ?", symbol).
		Find(&mappings).Error
	if err != nil {
		return nil, err
	}
	if len(mappings) == 0 {
		return list, nil
	}

	// Collect unique category codes
	categoryCodes := make([]string, 0, len(mappings))
	seen := make(map[string]bool)
	for _, m := range mappings {
		if !seen[m.CategoryCode] {
			categoryCodes = append(categoryCodes, m.CategoryCode)
			seen[m.CategoryCode] = true
		}
	}

	// Query 2: Fetch category details in batch
	type CategoryQuery struct {
		ID         uint64
		Code       string
		Name       string
		Level      uint8
		ParentCode string
	}
	var categories []CategoryQuery
	err = d.db.WithContext(ctx).
		Table("taxonomy_category").
		Select("id, code, name, level, parent_code").
		Where("code IN ?", categoryCodes).
		Find(&categories).Error
	if err != nil {
		return nil, err
	}

	// Build category lookup map
	categoryMap := make(map[string]*CategoryQuery)
	for i := range categories {
		categoryMap[categories[i].Code] = &categories[i]
	}

	// Merge results
	for _, m := range mappings {
		cat, ok := categoryMap[m.CategoryCode]
		detail := &model.TaxonomySecurityMapWithDetail{
			Source:       m.Source,
			Taxonomy:     m.Taxonomy,
			CategoryCode: m.CategoryCode,
			Symbol:       m.Symbol,
			AssetType:    m.AssetType,
			Market:       m.Market,
		}
		if ok {
			detail.ID = cat.ID
			detail.CategoryName = cat.Name
			detail.Level = cat.Level
			detail.ParentCode = cat.ParentCode
		}
		list = append(list, detail)
	}

	return list, nil
}

// DeleteMapping deletes a single mapping.
func (d *TaxonomyDao) DeleteMapping(ctx context.Context, source, taxonomy, categoryCode, symbol string) error {
	return d.db.WithContext(ctx).
		Where("source = ? AND taxonomy = ? AND category_code = ? AND symbol = ?", source, taxonomy, categoryCode, symbol).
		Delete(&model.TaxonomySecurityMap{}).Error
}

// ──────────── Industry Constituents ────────────

// BatchUpsertConstituents upserts industry index constituents.
func (d *TaxonomyDao) BatchUpsertConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	if len(list) == 0 {
		return nil
	}
	for _, c := range list {
		c.Source = source
		c.Taxonomy = taxonomy
		if market != "" {
			c.Market = market
		}
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "index_code"}, {Name: "symbol"}, {Name: "market"}},
			DoUpdates: clause.AssignmentColumns([]string{"con_code", "index_name", "in_date", "out_date", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListConstituentsByIndex returns all constituents for a given source + taxonomy + index_code.
func (d *TaxonomyDao) ListConstituentsByIndex(ctx context.Context, source, taxonomy, indexCode string, limit, offset int) ([]*model.IndustryConstituent, error) {
	var list []*model.IndustryConstituent
	q := d.db.WithContext(ctx).Where("source = ? AND taxonomy = ? AND index_code = ?", source, taxonomy, indexCode).Order("symbol ASC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	err := q.Find(&list).Error
	return list, err
}

// ListConstituentsBySymbol returns all index memberships for a given constituent stock.
func (d *TaxonomyDao) ListConstituentsBySymbol(ctx context.Context, source, taxonomy, symbol string) ([]*model.IndustryConstituent, error) {
	var list []*model.IndustryConstituent
	err := d.db.WithContext(ctx).Where("source = ? AND taxonomy = ? AND symbol = ?", source, taxonomy, symbol).Find(&list).Error
	return list, err
}

// ──────────── Industry Weights ────────────

// BatchUpsertWeights upserts industry index constituent daily weights.
func (d *TaxonomyDao) BatchUpsertWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	if len(list) == 0 {
		return nil
	}
	for _, w := range list {
		w.Source = source
		w.Taxonomy = taxonomy
		if market != "" {
			w.Market = market
		}
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "index_code"}, {Name: "symbol"}, {Name: "market"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns([]string{"con_code", "weight", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListWeightsByIndexAndDate returns weights for a given index on a given trade_date.
func (d *TaxonomyDao) ListWeightsByIndexAndDate(ctx context.Context, source, taxonomy, indexCode, tradeDate string) ([]*model.IndustryWeight, error) {
	var list []*model.IndustryWeight
	err := d.db.WithContext(ctx).
		Where("source = ? AND taxonomy = ? AND index_code = ? AND trade_date = ?", source, taxonomy, indexCode, tradeDate).
		Order("symbol ASC").
		Find(&list).Error
	return list, err
}

// ──────────── Industry Daily ────────────

// BatchUpsertIndustryDaily upserts industry index daily bars.
func (d *TaxonomyDao) BatchUpsertIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	if len(list) == 0 {
		return nil
	}
	for _, r := range list {
		r.Source = source
		r.Taxonomy = taxonomy
		if market != "" {
			r.Market = market
		}
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "index_code"}, {Name: "market"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns([]string{
				"open", "high", "close", "low", "pre_close",
				"amount", "volume", "pb", "pe", "total_cap", "a_float_cap", "updated_at",
			}),
		}).CreateInBatches(list, 500).Error
}

// QueryIndustryDaily queries industry daily bars.
func (d *TaxonomyDao) QueryIndustryDaily(ctx context.Context, source, taxonomy, indexCode, startDate, endDate string, limit int) ([]*model.IndustryDaily, error) {
	var list []*model.IndustryDaily
	q := d.db.WithContext(ctx).
		Where("source = ? AND taxonomy = ? AND index_code = ?", source, taxonomy, indexCode).
		Order("trade_date ASC")
	if startDate != "" {
		q = q.Where("trade_date >= ?", startDate)
	}
	if endDate != "" {
		q = q.Where("trade_date <= ?", endDate)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	err := q.Find(&list).Error
	return list, err
}
