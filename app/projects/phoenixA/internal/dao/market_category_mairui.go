package dao

import (
	"context"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type MarketCategoryMairui struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewMarketCategoryMairui(dsName string) *MarketCategoryMairui {
	return &MarketCategoryMairui{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_MARKET_CATEGORY_MAIRUI),
		dsName:        dsName,
	}
}

func (d *MarketCategoryMairui) Start(ctx context.Context) error {
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

func (d *MarketCategoryMairui) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *MarketCategoryMairui) Create(ctx context.Context, m *model.CategoryMairui) error {
	return d.db.WithContext(ctx).Create(m).Error
}

func (d *MarketCategoryMairui) Update(ctx context.Context, m *model.CategoryMairui) error {
	return d.db.WithContext(ctx).Model(&model.CategoryMairui{}).Where("code = ?", m.Code).Updates(m).Error
}

func (d *MarketCategoryMairui) BatchUpsert(ctx context.Context, list []*model.CategoryMairui, chunkSize int) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "code"}},
		DoUpdates: clause.AssignmentColumns([]string{"name", "parent_code", "parent_name", "level", "type1", "type2", "is_leaf"}),
	}).CreateInBatches(list, chunkSize).Error
}

func (d *MarketCategoryMairui) Get(ctx context.Context, code string) (*model.CategoryMairui, error) {
	var m model.CategoryMairui
	err := d.db.WithContext(ctx).Where("code = ?", code).First(&m).Error
	if err != nil {
		return nil, err
	}
	return &m, nil
}

func (d *MarketCategoryMairui) Delete(ctx context.Context, code string) error {
	return d.db.WithContext(ctx).Where("code = ?", code).Delete(&model.CategoryMairui{}).Error
}

func (d *MarketCategoryMairui) List(ctx context.Context, f *model.CategoryFiltersMairui, limit, offset int) ([]*model.CategoryMairui, error) {
	var list []*model.CategoryMairui
	query := d.db.WithContext(ctx)
	if f != nil {
		if f.ParentName != nil {
			query = query.Where("parent_name like ?", "%"+*f.ParentName+"%")
		}
		if f.ParentCode != nil {
			query = query.Where("parent_code = ?", *f.ParentCode)
		}
		if f.Level != nil {
			query = query.Where("level = ?", *f.Level)
		}
		if f.Type1 != nil {
			query = query.Where("type1 = ?", *f.Type1)
		}
		if f.Type2 != nil {
			query = query.Where("type2 = ?", *f.Type2)
		}
	}
	err := query.Limit(limit).Offset(offset).Find(&list).Error
	return list, err
}

func (d *MarketCategoryMairui) Count(ctx context.Context, f *model.CategoryFiltersMairui) (int64, error) {
	var count int64
	query := d.db.WithContext(ctx).Model(&model.CategoryMairui{})
	if f != nil {
		if f.ParentCode != nil {
			query = query.Where("parent_code = ?", *f.ParentCode)
		}
		if f.Level != nil {
			query = query.Where("level = ?", *f.Level)
		}
		if f.Type1 != nil {
			query = query.Where("type1 = ?", *f.Type1)
		}
		if f.Type2 != nil {
			query = query.Where("type2 = ?", *f.Type2)
		}
	}
	err := query.Count(&count).Error
	return count, err
}
