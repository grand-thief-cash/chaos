package dao

import (
	"context"
	"fmt"
	"strings"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// SecurityRegistryDao handles CRUD for the unified security registry table.
type SecurityRegistryDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewSecurityRegistryDao(dsName string) *SecurityRegistryDao {
	return &SecurityRegistryDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_SECURITY_REGISTRY, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

func (d *SecurityRegistryDao) Start(ctx context.Context) error {
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

func (d *SecurityRegistryDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *SecurityRegistryDao) BatchUpsert(ctx context.Context, list []*model.SecurityRegistry, chunkSize int) (int64, error) {
	if len(list) == 0 {
		return 0, nil
	}
	if chunkSize <= 0 {
		chunkSize = 200
	}
	for _, s := range list {
		s.ID = 0 // id is surrogate, auto-assigned; ignore any client-supplied value on upsert
		s.Symbol = strings.TrimSpace(s.Symbol)
		s.Exchange = strings.ToUpper(strings.TrimSpace(s.Exchange))
		s.Name = strings.TrimSpace(s.Name)
		if s.AssetType == "" {
			s.AssetType = bizConsts.ASSET_TYPE_STOCK
		}
		if s.Market == "" {
			s.Market = bizConsts.MARKET_ZH_A
		}
		if s.Status == "" {
			s.Status = "active"
		}
	}
	var affected int64
	for i := 0; i < len(list); i += chunkSize {
		end := i + chunkSize
		if end > len(list) {
			end = len(list)
		}
		batch := list[i:end]
		res := d.db.WithContext(ctx).
			Clauses(clause.OnConflict{
				Columns:   []clause.Column{{Name: "exchange"}, {Name: "asset_type"}, {Name: "symbol"}},
				DoUpdates: clause.AssignmentColumns([]string{"name", "full_name", "status", "list_date", "delist_date", "market", "updated_at"}),
			}).Create(&batch)
		if res.Error != nil {
			return affected, res.Error
		}
		affected += res.RowsAffected
	}
	return affected, nil
}

// Get retrieves a security by its natural key (exchange, asset_type, symbol).
// asset_type is expected to be passed explicitly (callers use consts.ASSET_TYPE_STOCK).
// exchange/symbol are normalized to match BatchUpsert's storage form, so callers
// may pass "sz"/" 000001 " and still resolve the row.
func (d *SecurityRegistryDao) Get(ctx context.Context, exchange, assetType, symbol string) (*model.SecurityRegistry, error) {
	exchange = strings.ToUpper(strings.TrimSpace(exchange))
	symbol = strings.TrimSpace(symbol)
	var s model.SecurityRegistry
	err := d.db.WithContext(ctx).
		Where("exchange = ? AND asset_type = ? AND symbol = ?", exchange, assetType, symbol).
		First(&s).Error
	if err != nil {
		return nil, err
	}
	return &s, nil
}

// GetByID retrieves a security by its surrogate id.
func (d *SecurityRegistryDao) GetByID(ctx context.Context, id uint64) (*model.SecurityRegistry, error) {
	var s model.SecurityRegistry
	err := d.db.WithContext(ctx).Where("id = ?", id).First(&s).Error
	if err != nil {
		return nil, err
	}
	return &s, nil
}

// GetAll returns all securities (ordered by symbol), used to build resolve caches.
func (d *SecurityRegistryDao) GetAll(ctx context.Context) ([]*model.SecurityRegistry, error) {
	return d.ListFiltered(ctx, nil, 0, 0)
}

func (d *SecurityRegistryDao) ListFiltered(ctx context.Context, f *model.SecurityFilters, limit, offset int) ([]*model.SecurityRegistry, error) {
	var list []*model.SecurityRegistry
	q := d.db.WithContext(ctx).Model(&model.SecurityRegistry{})
	if f != nil && f.Q != "" {
		// Exact-symbol (case-insensitive) tier first, then symbol ASC - mirrors
		// the in-memory SearchPage sort. Parameter-bound via clause.Expr so user
		// input never reaches raw SQL (no manual quote escaping, no dependence on
		// the DB's string-literal config).
		q = q.Clauses(clause.OrderBy{
			Expression: clause.Expr{
				SQL:  "CASE WHEN UPPER(symbol) = UPPER(?) THEN 0 ELSE 1 END, symbol ASC",
				Vars: []interface{}{strings.TrimSpace(f.Q)},
			},
		})
	} else {
		q = q.Order("symbol ASC")
	}
	q = applySecurityFilters(q, f)
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

func (d *SecurityRegistryDao) CountFiltered(ctx context.Context, f *model.SecurityFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.SecurityRegistry{})
	q = applySecurityFilters(q, f)
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}

func (d *SecurityRegistryDao) DeleteAll(ctx context.Context, assetType, market string) (int64, error) {
	q := d.db.WithContext(ctx)
	if assetType != "" {
		q = q.Where("asset_type = ?", assetType)
	}
	if market != "" {
		q = q.Where("market = ?", market)
	}
	res := q.Delete(&model.SecurityRegistry{})
	return res.RowsAffected, res.Error
}

// SecurityScopeHasReferences reports whether any downstream row references a
// security_id in the given (asset_type, market) scope — the same scope DeleteAll
// would remove. Guards delete against leaving dangling security_id references
// (no real FK, §6 R9 → app-layer defense; mirrors TaxonomyDao.CategoryHasReferences).
// Empty assetType/market means "all securities". Covers the Phase 2 taxonomy chain
// (taxonomy_security_map / industry_constituent / industry_weight) AND the Phase 3
// data tables (financial_statement / corporate_action / equity_structure /
// adjust_factor / long_hu_bang), all of which now reference security_id.
func (d *SecurityRegistryDao) SecurityScopeHasReferences(ctx context.Context, assetType, market string) (bool, error) {
	scope := func() *gorm.DB {
		q := d.db.WithContext(ctx).Model(&model.SecurityRegistry{}).Select("id")
		if assetType != "" {
			q = q.Where("asset_type = ?", assetType)
		}
		if market != "" {
			q = q.Where("market = ?", market)
		}
		return q
	}
	tables := []string{
		"ods.taxonomy_security_map",
		"ods.industry_constituent",
		"ods.industry_weight",
		"ods.financial_statement",
		"ods.corporate_action",
		"ods.equity_structure",
		"ods.adjust_factor",
		"ods.long_hu_bang",
	}
	for _, tbl := range tables {
		var c int64
		if err := d.db.WithContext(ctx).Table(tbl).Where("security_id IN (?)", scope()).Count(&c).Error; err != nil {
			return false, err
		}
		if c > 0 {
			return true, nil
		}
	}
	return false, nil
}

func applySecurityFilters(q *gorm.DB, f *model.SecurityFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if f.SecurityID != 0 {
		q = q.Where("id = ?", f.SecurityID)
	}
	if f.AssetType != "" {
		q = q.Where("asset_type = ?", f.AssetType)
	}
	if f.Market != "" {
		q = q.Where("market = ?", f.Market)
	}
	if f.Exchange != "" {
		q = q.Where("exchange = ?", strings.ToUpper(f.Exchange))
	}
	if len(f.Exchanges) > 0 {
		q = q.Where("exchange IN ?", f.Exchanges)
	}
	if f.Status != "" {
		q = q.Where("status = ?", f.Status)
	}
	if f.Name != "" {
		q = q.Where("name LIKE ?", "%"+strings.TrimSpace(f.Name)+"%")
	}
	if f.Q != "" {
		// Q: symbol exact (case-insensitive) OR name contains (case-sensitive).
		// % and _ are escaped to literals so a user q cannot inject LIKE wildcards.
		trimmed := strings.TrimSpace(f.Q)
		escaped := strings.NewReplacer("\\", "\\\\", "%", "\\%", "_", "\\_").Replace(trimmed)
		q = q.Where("UPPER(symbol) = UPPER(?) OR name LIKE ? ESCAPE '\\'", trimmed, "%"+escaped+"%")
	}
	if len(f.Symbols) > 0 {
		q = q.Where("symbol IN ?", f.Symbols)
	} else if f.Symbol != "" {
		q = q.Where("symbol = ?", strings.TrimSpace(f.Symbol))
	}
	return q
}
