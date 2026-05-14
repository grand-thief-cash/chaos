package dao

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

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
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "market"}, {Name: "code"}},
			DoUpdates: clause.AssignmentColumns([]string{"name", "parent_code", "index_code", "level", "is_leaf", "attrs_json", "updated_at"}),
		}).CreateInBatches(list, 500).Error; err != nil {
			return err
		}
		return d.upsertDerivedFlagsForCategories(ctx, tx, list)
	})
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

type taxonomyCategoryLookupKey struct {
	Source   string
	Taxonomy string
	Market   string
	Code     string
}

type taxonomyCategoryQuery struct {
	ID         uint64
	Source     string
	Taxonomy   string
	Market     string
	Code       string
	Name       string
	Level      uint8
	ParentCode *string
	IndexCode  *string
	AttrsJSON  *string
}

type taxonomyCategoryDerivedFlagsQuery struct {
	Source       string
	Taxonomy     string
	Market       string
	Code         string
	DerivedFlags *string
}

// ListMappingsBySymbol returns all taxonomy mappings for a given symbol.
// Loads matching taxonomy categories by full composite key and enriches the response
// with canonical hierarchy fields for downstream consumers.
func (d *TaxonomyDao) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMapWithDetail, error) {
	var list []*model.TaxonomySecurityMapWithDetail

	type MappingQuery struct {
		Source       string
		Taxonomy     string
		CategoryCode string
		Symbol       string
		AssetType    string
		Market       string
		CreatedAt    time.Time
		UpdatedAt    time.Time
	}
	var mappings []MappingQuery
	err := d.db.WithContext(ctx).
		Table("taxonomy_security_map").
		Select("source, taxonomy, category_code, symbol, asset_type, market, created_at, updated_at").
		Where("symbol = ?", symbol).
		Find(&mappings).Error
	if err != nil {
		return nil, err
	}
	if len(mappings) == 0 {
		return list, nil
	}

	categoryKeys := make([]taxonomyCategoryLookupKey, 0, len(mappings))
	seen := make(map[taxonomyCategoryLookupKey]bool)
	for _, m := range mappings {
		key := taxonomyCategoryLookupKey{
			Source:   m.Source,
			Taxonomy: m.Taxonomy,
			Market:   m.Market,
			Code:     m.CategoryCode,
		}
		if !seen[key] {
			categoryKeys = append(categoryKeys, key)
			seen[key] = true
		}
	}

	categoryMap, err := d.loadCategoryTree(ctx, categoryKeys)
	if err != nil {
		return nil, err
	}
	derivedFlagsMap, err := d.loadDerivedFlags(ctx, categoryKeys)
	if err != nil {
		return nil, err
	}

	for _, m := range mappings {
		key := taxonomyCategoryLookupKey{
			Source:   m.Source,
			Taxonomy: m.Taxonomy,
			Market:   m.Market,
			Code:     m.CategoryCode,
		}
		cat, ok := categoryMap[key]
		canonicalSource, canonicalTaxonomy, canonicalLevel := canonicalTaxonomyInfo(m.Source, m.Taxonomy, 0)
		detail := &model.TaxonomySecurityMapWithDetail{
			Source:                m.Source,
			Taxonomy:              m.Taxonomy,
			CategoryCode:          m.CategoryCode,
			CanonicalSource:       canonicalSource,
			CanonicalTaxonomy:     canonicalTaxonomy,
			CanonicalLevel:        canonicalLevel,
			CanonicalCategoryCode: m.CategoryCode,
			DerivedFlags:          map[string]bool{},
			Symbol:                m.Symbol,
			AssetType:             m.AssetType,
			Market:                m.Market,
			CreatedAt:             m.CreatedAt,
			UpdatedAt:             m.UpdatedAt,
		}
		if ok {
			detail.ID = cat.ID
			detail.CategoryName = cat.Name
			detail.Level = cat.Level
			detail.CanonicalSource, detail.CanonicalTaxonomy, detail.CanonicalLevel = canonicalTaxonomyInfo(m.Source, m.Taxonomy, cat.Level)
			detail.CanonicalCategoryCode = cat.Code
			detail.CanonicalCategoryName = cat.Name
			detail.DerivedFlags = deriveCategoryFlags(cat, categoryMap, derivedFlagsMap[key], detail.CanonicalTaxonomy)
			if cat.ParentCode != nil {
				detail.ParentCode = *cat.ParentCode
				detail.CanonicalParentCode = *cat.ParentCode
			}
			if cat.IndexCode != nil {
				detail.IndexCode = *cat.IndexCode
				detail.CanonicalIndexCode = *cat.IndexCode
			}
		}
		list = append(list, detail)
	}

	return list, nil
}

func (d *TaxonomyDao) upsertDerivedFlagsForCategories(ctx context.Context, tx *gorm.DB, categories []*model.TaxonomyCategory) error {
	keys := make([]taxonomyCategoryLookupKey, 0, len(categories))
	for _, cat := range categories {
		keys = append(keys, taxonomyCategoryLookupKey{
			Source:   cat.Source,
			Taxonomy: cat.Taxonomy,
			Market:   cat.Market,
			Code:     cat.Code,
		})
	}
	keys = dedupeCategoryLookupKeys(keys)
	if len(keys) == 0 {
		return nil
	}

	categoryMap, err := d.loadCategoryTreeWithDB(ctx, tx, keys)
	if err != nil {
		return err
	}
	existingFlags, err := d.loadDerivedFlagsWithDB(ctx, tx, keys)
	if err != nil {
		return err
	}

	records := make([]*model.TaxonomyCategoryDerivedFlags, 0, len(keys))
	for _, key := range keys {
		cat := categoryMap[key]
		if cat == nil {
			continue
		}
		_, canonicalTaxonomy, _ := canonicalTaxonomyInfo(cat.Source, cat.Taxonomy, cat.Level)
		flags := deriveCategoryFlags(cat, categoryMap, existingFlags[key], canonicalTaxonomy)
		if len(flags) == 0 {
			continue
		}
		payloadBytes, err := json.Marshal(flags)
		if err != nil {
			return err
		}
		payload := string(payloadBytes)
		records = append(records, &model.TaxonomyCategoryDerivedFlags{
			Source:       key.Source,
			Taxonomy:     key.Taxonomy,
			Market:       key.Market,
			Code:         key.Code,
			DerivedFlags: &payload,
		})
	}
	if len(records) == 0 {
		return nil
	}
	return tx.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "source"}, {Name: "taxonomy"}, {Name: "market"}, {Name: "code"}},
		DoUpdates: clause.AssignmentColumns([]string{"derived_flags", "updated_at"}),
	}).CreateInBatches(records, 500).Error
}

func (d *TaxonomyDao) loadCategoryTree(ctx context.Context, initialKeys []taxonomyCategoryLookupKey) (map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery, error) {
	return d.loadCategoryTreeWithDB(ctx, d.db, initialKeys)
}

func (d *TaxonomyDao) loadCategoryTreeWithDB(ctx context.Context, db *gorm.DB, initialKeys []taxonomyCategoryLookupKey) (map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery, error) {
	categoryMap := make(map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery)
	pending := dedupeCategoryLookupKeys(initialKeys)

	for len(pending) > 0 {
		sources := make([]string, 0, len(pending))
		taxonomies := make([]string, 0, len(pending))
		markets := make([]string, 0, len(pending))
		codes := make([]string, 0, len(pending))
		sourceSeen := make(map[string]bool)
		taxonomySeen := make(map[string]bool)
		marketSeen := make(map[string]bool)
		codeSeen := make(map[string]bool)
		for _, key := range pending {
			if key.Source != "" && !sourceSeen[key.Source] {
				sources = append(sources, key.Source)
				sourceSeen[key.Source] = true
			}
			if key.Taxonomy != "" && !taxonomySeen[key.Taxonomy] {
				taxonomies = append(taxonomies, key.Taxonomy)
				taxonomySeen[key.Taxonomy] = true
			}
			if key.Market != "" && !marketSeen[key.Market] {
				markets = append(markets, key.Market)
				marketSeen[key.Market] = true
			}
			if key.Code != "" && !codeSeen[key.Code] {
				codes = append(codes, key.Code)
				codeSeen[key.Code] = true
			}
		}

		if len(sources) == 0 || len(taxonomies) == 0 || len(markets) == 0 || len(codes) == 0 {
			break
		}

		var categories []taxonomyCategoryQuery
		err := db.WithContext(ctx).
			Table("taxonomy_category").
			Select("id, source, taxonomy, market, code, name, level, parent_code, index_code, attrs_json").
			Where("source IN ? AND taxonomy IN ? AND market IN ? AND code IN ?", sources, taxonomies, markets, codes).
			Find(&categories).Error
		if err != nil {
			return nil, err
		}

		nextPending := make([]taxonomyCategoryLookupKey, 0)
		nextSeen := make(map[taxonomyCategoryLookupKey]bool)
		for i := range categories {
			cat := &categories[i]
			key := taxonomyCategoryLookupKey{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}
			categoryMap[key] = cat
			if cat.ParentCode != nil && *cat.ParentCode != "" {
				parentKey := taxonomyCategoryLookupKey{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: *cat.ParentCode}
				if _, ok := categoryMap[parentKey]; !ok && !nextSeen[parentKey] {
					nextPending = append(nextPending, parentKey)
					nextSeen[parentKey] = true
				}
			}
		}
		pending = nextPending
	}

	return categoryMap, nil
}

func (d *TaxonomyDao) loadDerivedFlags(ctx context.Context, keys []taxonomyCategoryLookupKey) (map[taxonomyCategoryLookupKey]map[string]bool, error) {
	return d.loadDerivedFlagsWithDB(ctx, d.db, keys)
}

func (d *TaxonomyDao) loadDerivedFlagsWithDB(ctx context.Context, db *gorm.DB, keys []taxonomyCategoryLookupKey) (map[taxonomyCategoryLookupKey]map[string]bool, error) {
	result := make(map[taxonomyCategoryLookupKey]map[string]bool)
	keys = dedupeCategoryLookupKeys(keys)
	if len(keys) == 0 {
		return result, nil
	}

	sources := make([]string, 0)
	taxonomies := make([]string, 0)
	markets := make([]string, 0)
	codes := make([]string, 0)
	sourceSeen := make(map[string]bool)
	taxonomySeen := make(map[string]bool)
	marketSeen := make(map[string]bool)
	codeSeen := make(map[string]bool)
	for _, key := range keys {
		if key.Source != "" && !sourceSeen[key.Source] {
			sources = append(sources, key.Source)
			sourceSeen[key.Source] = true
		}
		if key.Taxonomy != "" && !taxonomySeen[key.Taxonomy] {
			taxonomies = append(taxonomies, key.Taxonomy)
			taxonomySeen[key.Taxonomy] = true
		}
		if key.Market != "" && !marketSeen[key.Market] {
			markets = append(markets, key.Market)
			marketSeen[key.Market] = true
		}
		if key.Code != "" && !codeSeen[key.Code] {
			codes = append(codes, key.Code)
			codeSeen[key.Code] = true
		}
	}

	var rows []taxonomyCategoryDerivedFlagsQuery
	if err := db.WithContext(ctx).
		Table("taxonomy_category_derived_flags").
		Select("source, taxonomy, market, code, derived_flags").
		Where("source IN ? AND taxonomy IN ? AND market IN ? AND code IN ?", sources, taxonomies, markets, codes).
		Find(&rows).Error; err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "does not exist") || strings.Contains(strings.ToLower(err.Error()), "no such table") {
			return result, nil
		}
		return nil, err
	}

	for _, row := range rows {
		flags := parseBoolMapJSON(row.DerivedFlags)
		if len(flags) == 0 {
			continue
		}
		result[taxonomyCategoryLookupKey{Source: row.Source, Taxonomy: row.Taxonomy, Market: row.Market, Code: row.Code}] = flags
	}
	return result, nil
}

func dedupeCategoryLookupKeys(keys []taxonomyCategoryLookupKey) []taxonomyCategoryLookupKey {
	result := make([]taxonomyCategoryLookupKey, 0, len(keys))
	seen := make(map[taxonomyCategoryLookupKey]bool)
	for _, key := range keys {
		if key.Source == "" || key.Taxonomy == "" || key.Market == "" || key.Code == "" {
			continue
		}
		if seen[key] {
			continue
		}
		seen[key] = true
		result = append(result, key)
	}
	return result
}

func canonicalTaxonomyInfo(source, taxonomy string, level uint8) (string, string, uint8) {
	canonicalFamily := canonicalTaxonomyFamily(taxonomy, source)
	canonicalLevel := level
	if canonicalLevel == 0 {
		canonicalLevel = parseTaxonomyLevel(taxonomy)
	}
	return canonicalFamily, canonicalFamily, canonicalLevel
}

func canonicalTaxonomyFamily(values ...string) string {
	for _, value := range values {
		normalized := strings.ToLower(strings.TrimSpace(value))
		switch {
		case normalized == "swhy", strings.HasPrefix(normalized, "sw"):
			return "sw"
		case strings.HasPrefix(normalized, "citics"), strings.HasPrefix(normalized, "citic"):
			return "citics"
		}
	}
	return ""
}

func parseTaxonomyLevel(taxonomy string) uint8 {
	normalized := strings.ToLower(strings.TrimSpace(taxonomy))
	idx := strings.LastIndex(normalized, "_l")
	if idx < 0 || idx+2 >= len(normalized) {
		return 0
	}
	level, err := strconv.Atoi(normalized[idx+2:])
	if err != nil || level <= 0 || level > 255 {
		return 0
	}
	return uint8(level)
}

func deriveCategoryFlags(cat *taxonomyCategoryQuery, categoryMap map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery, persistedFlags map[string]bool, canonicalTaxonomy string) map[string]bool {
	flags := cloneBoolMap(persistedFlags)
	if len(flags) == 0 {
		flags = parseDerivedFlags(cat)
	}
	if flags == nil {
		flags = make(map[string]bool)
	}
	if _, ok := flags["financial_sector"]; !ok {
		flags["financial_sector"] = isFinancialSectorCategory(cat, categoryMap, canonicalTaxonomy)
	}
	return flags
}

func parseDerivedFlags(cat *taxonomyCategoryQuery) map[string]bool {
	if cat == nil || cat.AttrsJSON == nil || strings.TrimSpace(*cat.AttrsJSON) == "" {
		return nil
	}

	var payload map[string]any
	if err := json.Unmarshal([]byte(*cat.AttrsJSON), &payload); err != nil {
		return nil
	}

	flags := make(map[string]bool)
	mergeBoolMap(flags, payload["derived_flags"])
	if value, ok := payload["is_financial_sector"].(bool); ok {
		flags["financial_sector"] = value
	}
	if len(flags) == 0 {
		return nil
	}
	return flags
}

func parseBoolMapJSON(raw *string) map[string]bool {
	if raw == nil || strings.TrimSpace(*raw) == "" {
		return nil
	}
	var payload any
	if err := json.Unmarshal([]byte(*raw), &payload); err != nil {
		return nil
	}
	flags := make(map[string]bool)
	mergeBoolMap(flags, payload)
	if len(flags) == 0 {
		return nil
	}
	return flags
}

func mergeBoolMap(dst map[string]bool, raw any) {
	nested, ok := raw.(map[string]any)
	if !ok {
		return
	}
	for key, value := range nested {
		if boolVal, ok := value.(bool); ok {
			dst[key] = boolVal
		}
	}
}

func cloneBoolMap(src map[string]bool) map[string]bool {
	if len(src) == 0 {
		return nil
	}
	dst := make(map[string]bool, len(src))
	for key, value := range src {
		dst[key] = value
	}
	return dst
}

func isFinancialSectorCategory(cat *taxonomyCategoryQuery, categoryMap map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery, canonicalTaxonomy string) bool {
	current := cat
	visited := make(map[taxonomyCategoryLookupKey]bool)
	for current != nil {
		if categoryLooksFinancial(current, canonicalTaxonomy) {
			return true
		}
		if current.ParentCode == nil || *current.ParentCode == "" {
			break
		}
		parentKey := taxonomyCategoryLookupKey{Source: current.Source, Taxonomy: current.Taxonomy, Market: current.Market, Code: *current.ParentCode}
		if visited[parentKey] {
			break
		}
		visited[parentKey] = true
		current = categoryMap[parentKey]
	}
	return false
}

func categoryLooksFinancial(cat *taxonomyCategoryQuery, canonicalTaxonomy string) bool {
	name := strings.TrimSpace(cat.Name)
	for _, keyword := range []string{"银行", "保险", "证券", "多元金融", "非银金融", "综合金融", "金融"} {
		if name != "" && strings.Contains(name, keyword) {
			return true
		}
	}
	if canonicalTaxonomy != "sw" {
		return false
	}
	code := strings.TrimSpace(cat.Code)
	return code == "801010" || code == "801780" || strings.HasPrefix(code, "80101") || strings.HasPrefix(code, "80178")
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
