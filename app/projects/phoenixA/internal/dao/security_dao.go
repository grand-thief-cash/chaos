package dao

import (
	"context"
	"fmt"
	"strings"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
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
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
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
				Columns:   []clause.Column{{Name: "symbol"}, {Name: "asset_type"}, {Name: "market"}},
				DoUpdates: clause.AssignmentColumns([]string{"exchange", "name", "full_name", "status", "list_date", "delist_date", "updated_at"}),
			}).Create(&batch)
		if res.Error != nil {
			return affected, res.Error
		}
		affected += res.RowsAffected
	}
	return affected, nil
}

func (d *SecurityRegistryDao) Get(ctx context.Context, symbol, assetType, market string) (*model.SecurityRegistry, error) {
	var s model.SecurityRegistry
	err := d.db.WithContext(ctx).
		Where("symbol = ? AND asset_type = ? AND market = ?", symbol, assetType, market).
		First(&s).Error
	if err != nil {
		return nil, err
	}
	return &s, nil
}

func (d *SecurityRegistryDao) ListFiltered(ctx context.Context, f *model.SecurityFilters, limit, offset int) ([]*model.SecurityRegistry, error) {
	var list []*model.SecurityRegistry
	q := d.db.WithContext(ctx).Model(&model.SecurityRegistry{}).Order("symbol ASC")
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

func applySecurityFilters(q *gorm.DB, f *model.SecurityFilters) *gorm.DB {
	if f == nil {
		return q
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
	if len(f.Symbols) > 0 {
		q = q.Where("symbol IN ?", f.Symbols)
	} else if f.Symbol != "" {
		q = q.Where("symbol = ?", strings.TrimSpace(f.Symbol))
	}
	return q
}
