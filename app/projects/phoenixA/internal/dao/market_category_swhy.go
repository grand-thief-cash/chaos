package dao

import (
	"context"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type MarketCategorySWHY struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewMarketCategorySWHY(dsName string) *MarketCategorySWHY {
	return &MarketCategorySWHY{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_MARKET_CATEGORY_SWHY),
		dsName:        dsName,
	}
}

func (d *MarketCategorySWHY) Start(ctx context.Context) error {
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

func (d *MarketCategorySWHY) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func (d *MarketCategorySWHY) Create(ctx context.Context, m *model.CategorySWHY) error {
	return d.db.WithContext(ctx).Create(m).Error
}

func (d *MarketCategorySWHY) Update(ctx context.Context, m *model.CategorySWHY) error {
	return d.db.WithContext(ctx).Model(&model.CategorySWHY{}).Where("industry_code = ?", m.IndustryCode).Updates(m).Error
}

func (d *MarketCategorySWHY) BatchUpsert(ctx context.Context, list []*model.CategorySWHY, chunkSize int) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "industry_code"}},
		DoUpdates: clause.AssignmentColumns([]string{"index_code", "level_code", "level1_name", "level2_name", "level3_name", "is_pub", "change_reason"}),
	}).CreateInBatches(list, chunkSize).Error
}

func (d *MarketCategorySWHY) Get(ctx context.Context, code string) (*model.CategorySWHY, error) {
	var m model.CategorySWHY
	err := d.db.WithContext(ctx).Where("industry_code = ?", code).First(&m).Error
	if err != nil {
		return nil, err
	}
	return &m, nil
}

func (d *MarketCategorySWHY) Delete(ctx context.Context, code string) error {
	return d.db.WithContext(ctx).Where("industry_code = ?", code).Delete(&model.CategorySWHY{}).Error
}

func (d *MarketCategorySWHY) List(ctx context.Context, filters *model.CategoryFiltersSWHY, limit, offset int) ([]*model.CategorySWHY, error) {
	var list []*model.CategorySWHY
	query := d.db.WithContext(ctx)
	if filters != nil {
		if filters.IndexCode != nil {
			query = query.Where("index_code = ?", *filters.IndexCode)
		}
		if filters.IndustryCode != nil {
			query = query.Where("industry_code = ?", *filters.IndustryCode)
		}
		if filters.LevelCode != nil {
			query = query.Where("level_code = ?", *filters.LevelCode)
		}
		if filters.Level1Name != nil {
			query = query.Where("level1_name like ?", "%"+*filters.Level1Name+"%")
		}
		if filters.Level2Name != nil {
			query = query.Where("level2_name like ?", "%"+*filters.Level2Name+"%")
		}
		if filters.Level3Name != nil {
			query = query.Where("level3_name like ?", "%"+*filters.Level3Name+"%")
		}
		if filters.IsPub != nil {
			query = query.Where("is_pub = ?", *filters.IsPub)
		}
	}
	err := query.Limit(limit).Offset(offset).Find(&list).Error
	return list, err
}

func (d *MarketCategorySWHY) Count(ctx context.Context, filters *model.CategoryFiltersSWHY) (int64, error) {
	var count int64
	query := d.db.WithContext(ctx).Model(&model.CategorySWHY{})
	if filters != nil {
		if filters.IndexCode != nil {
			query = query.Where("index_code = ?", *filters.IndexCode)
		}
		if filters.IndustryCode != nil {
			query = query.Where("industry_code = ?", *filters.IndustryCode)
		}
		if filters.LevelCode != nil {
			query = query.Where("level_code = ?", *filters.LevelCode)
		}
		if filters.Level1Name != nil {
			query = query.Where("level1_name like ?", "%"+*filters.Level1Name+"%")
		}
		if filters.Level2Name != nil {
			query = query.Where("level2_name like ?", "%"+*filters.Level2Name+"%")
		}
		if filters.Level3Name != nil {
			query = query.Where("level3_name like ?", "%"+*filters.Level3Name+"%")
		}
		if filters.IsPub != nil {
			query = query.Where("is_pub = ?", *filters.IsPub)
		}
	}
	err := query.Count(&count).Error
	return count, err
}
