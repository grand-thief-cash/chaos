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

// CategoryHasReferences reports whether any taxonomy_security_map / industry_constituent /
// industry_weight / industry_daily row references the given category_id. Guards category
// deletion against leaving dangling category_id references (no real FK, §6 R9 → app-layer
// defense). Hyperatables are queried by category_id index; no JOINs.
func (d *TaxonomyDao) CategoryHasReferences(ctx context.Context, categoryID uint64) (bool, error) {
	var count int64
	err := d.db.WithContext(ctx).Raw(`
		SELECT
			(SELECT COUNT(*) FROM ods.taxonomy_security_map WHERE category_id = ?) +
			(SELECT COUNT(*) FROM ods.industry_constituent WHERE category_id = ?) +
			(SELECT COUNT(*) FROM ods.industry_weight     WHERE category_id = ?) +
			(SELECT COUNT(*) FROM ods.industry_daily      WHERE category_id = ?)
	`, categoryID, categoryID, categoryID, categoryID).Scan(&count).Error
	if err != nil {
		return false, err
	}
	return count > 0, nil
}

// ──────────── Security Mappings ────────────

// SyncMappingsFromConstituents derives category→security mappings from industry_constituent.
// Phase 2 surrogate-key refactor: the JOIN with taxonomy_category is eliminated —
// industry_constituent rows already carry (category_id, security_id) resolved at upsert
// time (refactor §2.3), so this is now a single-table SELECT DISTINCT. The path's
// (source, taxonomy, market) is resolved by the service into a set of category_ids which
// scope the SELECT (otherwise it would span every taxonomy).
func (d *TaxonomyDao) SyncMappingsFromConstituents(ctx context.Context, categoryIDs []uint64) (int64, error) {
	if len(categoryIDs) == 0 {
		return 0, nil
	}
	sql := `
		INSERT INTO ods.taxonomy_security_map (security_id, category_id)
		SELECT DISTINCT security_id, category_id
		FROM ods.industry_constituent
		WHERE category_id IN ?
		  AND security_id IS NOT NULL
		  AND category_id IS NOT NULL
		ON CONFLICT (security_id, category_id) DO NOTHING
	`
	result := d.db.WithContext(ctx).Exec(sql, categoryIDs)
	if result.Error != nil {
		return 0, result.Error
	}
	return result.RowsAffected, nil
}

// BatchUpsertMappings upserts taxonomy-security mappings (id-keyed).
func (d *TaxonomyDao) BatchUpsertMappings(ctx context.Context, list []*model.TaxonomySecurityMap) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{DoNothing: true}).
		CreateInBatches(list, 500).Error
}

// ReplaceSecuritiesForCategories replaces all securities for given categories.
// payload: category_id → []security_id.
func (d *TaxonomyDao) ReplaceSecuritiesForCategories(ctx context.Context, payload map[uint64][]uint64) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		categories := make([]uint64, 0, len(payload))
		for cat := range payload {
			categories = append(categories, cat)
		}
		if len(categories) == 0 {
			return nil
		}
		if err := tx.Where("category_id IN ?", categories).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for cat, secs := range payload {
			for _, sec := range secs {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					SecurityID: sec,
					CategoryID: cat,
				})
			}
		}
		if len(toInsert) > 0 {
			return tx.CreateInBatches(toInsert, 500).Error
		}
		return nil
	})
}

// ReplaceCategoriesForSecurities replaces all categories for given securities.
// payload: security_id → []category_id.
func (d *TaxonomyDao) ReplaceCategoriesForSecurities(ctx context.Context, payload map[uint64][]uint64) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		securities := make([]uint64, 0, len(payload))
		for sec := range payload {
			securities = append(securities, sec)
		}
		if len(securities) == 0 {
			return nil
		}
		if err := tx.Where("security_id IN ?", securities).Delete(&model.TaxonomySecurityMap{}).Error; err != nil {
			return err
		}
		var toInsert []*model.TaxonomySecurityMap
		for sec, cats := range payload {
			for _, cat := range cats {
				toInsert = append(toInsert, &model.TaxonomySecurityMap{
					SecurityID: sec,
					CategoryID: cat,
				})
			}
		}
		if len(toInsert) > 0 {
			return tx.CreateInBatches(toInsert, 500).Error
		}
		return nil
	})
}

// ListMappingsByCategory returns all security mappings for a category_id.
func (d *TaxonomyDao) ListMappingsByCategory(ctx context.Context, categoryID uint64, limit, offset int) ([]*model.TaxonomySecurityMap, error) {
	var list []*model.TaxonomySecurityMap
	q := d.db.WithContext(ctx).Where("category_id = ?", categoryID)
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

// ListMappingsBySecurityID returns all taxonomy mappings for a given security_id.
// Phase 2 surrogate-key refactor: the mapping row is (security_id, category_id); category
// hierarchy fields are loaded via loadCategoryTreeByIDs. Security display fields (symbol /
// asset_type / market) are left empty here and filled by the service via the resolve cache.
type mappingQuery struct {
	SecurityID uint64
	CategoryID uint64
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

func (d *TaxonomyDao) ListMappingsBySecurityID(ctx context.Context, securityID uint64) ([]*model.TaxonomySecurityMapWithDetail, error) {
	var list []*model.TaxonomySecurityMapWithDetail

	var mappings []mappingQuery
	err := d.db.WithContext(ctx).
		Table("taxonomy_security_map").
		Select("security_id, category_id, created_at, updated_at").
		Where("security_id = ?", securityID).
		Find(&mappings).Error
	if err != nil {
		return nil, err
	}
	if len(mappings) == 0 {
		return list, nil
	}

	categoryIDs := make([]uint64, 0, len(mappings))
	seen := make(map[uint64]bool)
	for _, m := range mappings {
		if !seen[m.CategoryID] {
			categoryIDs = append(categoryIDs, m.CategoryID)
			seen[m.CategoryID] = true
		}
	}

	categoryByID, err := d.loadCategoryTreeByIDs(ctx, categoryIDs)
	if err != nil {
		return nil, err
	}
	// deriveCategoryFlags walks the parent chain by natural key, so build a natural-key
	// view of the same loaded tree. loadDerivedFlags is also keyed by natural key.
	categoryByNatural := make(map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery, len(categoryByID))
	for _, cat := range categoryByID {
		if cat == nil {
			continue
		}
		categoryByNatural[taxonomyCategoryLookupKey{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}] = cat
	}
	derivedFlagsMap, err := d.loadDerivedFlags(ctx, keysFromCategoryTree(categoryByNatural))
	if err != nil {
		return nil, err
	}

	for _, m := range mappings {
		cat := categoryByID[m.CategoryID]
		detail := &model.TaxonomySecurityMapWithDetail{
			SecurityID:   m.SecurityID,
			CategoryID:   m.CategoryID,
			CreatedAt:    m.CreatedAt,
			UpdatedAt:    m.UpdatedAt,
			DerivedFlags: map[string]bool{},
		}
		if cat != nil {
			detail.Source = cat.Source
			detail.Taxonomy = cat.Taxonomy
			detail.CategoryCode = cat.Code
			detail.CategoryName = cat.Name
			detail.Level = cat.Level
			natKey := taxonomyCategoryLookupKey{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code}
			canonicalSource, canonicalTaxonomy, canonicalLevel := canonicalTaxonomyInfo(cat.Source, cat.Taxonomy, cat.Level)
			detail.CanonicalSource = canonicalSource
			detail.CanonicalTaxonomy = canonicalTaxonomy
			detail.CanonicalLevel = canonicalLevel
			detail.CanonicalCategoryCode = cat.Code
			detail.CanonicalCategoryName = cat.Name
			detail.Market = cat.Market
			detail.DerivedFlags = deriveCategoryFlags(cat, categoryByNatural, derivedFlagsMap[natKey], canonicalTaxonomy)
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

// keysFromCategoryTree returns the natural-key set of a category tree map.
func keysFromCategoryTree(m map[taxonomyCategoryLookupKey]*taxonomyCategoryQuery) []taxonomyCategoryLookupKey {
	keys := make([]taxonomyCategoryLookupKey, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

// loadCategoryTreeByIDs loads taxonomy_category rows by id and walks their parent chain
// (parent_code). Returns a map keyed by category id covering both the requested nodes and
// their ancestors (so deriveCategoryFlags can walk the hierarchy).
func (d *TaxonomyDao) loadCategoryTreeByIDs(ctx context.Context, ids []uint64) (map[uint64]*taxonomyCategoryQuery, error) {
	byID := make(map[uint64]*taxonomyCategoryQuery)
	pending := make([]uint64, 0, len(ids))
	seen := make(map[uint64]bool)
	for _, id := range ids {
		if id != 0 && !seen[id] {
			seen[id] = true
			pending = append(pending, id)
		}
	}
	if len(pending) == 0 {
		return byID, nil
	}

	var rows []taxonomyCategoryQuery
	err := d.db.WithContext(ctx).
		Table("taxonomy_category").
		Select("id, source, taxonomy, market, code, name, level, parent_code, index_code, attrs_json").
		Where("id IN ?", pending).
		Find(&rows).Error
	if err != nil {
		return nil, err
	}

	natKeys := make([]taxonomyCategoryLookupKey, 0, len(rows))
	for i := range rows {
		cat := &rows[i]
		if cat.ID != 0 {
			byID[cat.ID] = cat
		}
		natKeys = append(natKeys, taxonomyCategoryLookupKey{Source: cat.Source, Taxonomy: cat.Taxonomy, Market: cat.Market, Code: cat.Code})
	}

	// Walk the parent chain via the existing natural-key tree loader (loads ancestors).
	tree, err := d.loadCategoryTreeWithDB(ctx, d.db, natKeys)
	if err != nil {
		return nil, err
	}
	for _, c := range tree {
		if c != nil && c.ID != 0 {
			byID[c.ID] = c
		}
	}
	return byID, nil
}

// ListAllCategories returns every taxonomy_category row, used to build the resolve cache.
func (d *TaxonomyDao) ListAllCategories(ctx context.Context) ([]*model.TaxonomyCategory, error) {
	var list []*model.TaxonomyCategory
	err := d.db.WithContext(ctx).Order("id ASC").Find(&list).Error
	return list, err
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

// DeleteMapping deletes a single mapping by (category_id, security_id).
func (d *TaxonomyDao) DeleteMapping(ctx context.Context, categoryID, securityID uint64) error {
	return d.db.WithContext(ctx).
		Where("category_id = ? AND security_id = ?", categoryID, securityID).
		Delete(&model.TaxonomySecurityMap{}).Error
}

// ──────────── Industry Constituents ────────────

// BatchUpsertConstituents upserts industry index constituents.
// Phase 2: items must already carry resolved (CategoryID, SecurityID) — the service
// resolves IndexCode/ConCode via the in-memory cache before calling this. source/taxonomy/
// market are retained for scope context only (no longer stored on the row).
func (d *TaxonomyDao) BatchUpsertConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "category_id"}, {Name: "security_id"}},
			DoUpdates: clause.AssignmentColumns([]string{"in_date", "out_date", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListConstituentsByCategory returns all constituents for a given category_id.
func (d *TaxonomyDao) ListConstituentsByCategory(ctx context.Context, categoryID uint64, limit, offset int) ([]*model.IndustryConstituent, error) {
	var list []*model.IndustryConstituent
	q := d.db.WithContext(ctx).Where("category_id = ?", categoryID).Order("security_id ASC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	err := q.Find(&list).Error
	return list, err
}

// ListConstituentsBySecurity returns all index memberships for a given constituent security_id.
func (d *TaxonomyDao) ListConstituentsBySecurity(ctx context.Context, securityID uint64) ([]*model.IndustryConstituent, error) {
	var list []*model.IndustryConstituent
	q := d.db.WithContext(ctx).Where("security_id = ?", securityID)
	err := q.Find(&list).Error
	return list, err
}

// ──────────── Industry Weights ────────────

// BatchUpsertWeights upserts industry index constituent daily weights.
// Phase 2: items must already carry resolved (CategoryID, SecurityID). source/taxonomy/
// market retained for scope context only.
func (d *TaxonomyDao) BatchUpsertWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "category_id"}, {Name: "security_id"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns([]string{"weight", "updated_at"}),
		}).CreateInBatches(list, 500).Error
}

// ListWeightsByCategoryAndDate returns weights for a given category_id on a given trade_date.
func (d *TaxonomyDao) ListWeightsByCategoryAndDate(ctx context.Context, categoryID uint64, tradeDate string) ([]*model.IndustryWeight, error) {
	var list []*model.IndustryWeight
	q := d.db.WithContext(ctx).
		Where("category_id = ? AND trade_date = ?", categoryID, tradeDate).
		Order("security_id ASC")
	err := q.Find(&list).Error
	return list, err
}

// ──────────── Industry Daily ────────────

// BatchUpsertIndustryDaily upserts industry index daily bars.
// Phase 2: items must already carry resolved CategoryID. source/taxonomy/market retained
// for scope context only.
func (d *TaxonomyDao) BatchUpsertIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{{Name: "category_id"}, {Name: "trade_date"}},
			DoUpdates: clause.AssignmentColumns([]string{
				"open", "high", "close", "low", "pre_close",
				"amount", "volume", "pb", "pe", "total_cap", "a_float_cap", "updated_at",
			}),
		}).CreateInBatches(list, 500).Error
}

// QueryIndustryDaily queries industry daily bars by category_id.
func (d *TaxonomyDao) QueryIndustryDaily(ctx context.Context, categoryID uint64, startDate, endDate string, limit int) ([]*model.IndustryDaily, error) {
	var list []*model.IndustryDaily
	q := d.db.WithContext(ctx).
		Where("category_id = ?", categoryID).
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
