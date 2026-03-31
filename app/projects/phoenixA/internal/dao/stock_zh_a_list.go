package dao

import (
	"context"
	"fmt"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type StockZhAListDao interface {
	// Embed component so registry builders can return it where core.Component is required.
	core.Component

	Create(ctx context.Context, s *model.StockZhAList) error
	// BatchUpsert inserts rows in batches. If primary key (code) already exists, it updates company/exchange.
	BatchUpsert(ctx context.Context, list []*model.StockZhAList, chunkSize int) (int64, error)
	Get(ctx context.Context, code string) (*model.StockZhAList, error)
	Update(ctx context.Context, s *model.StockZhAList) error
	// DeleteAll deletes all rows in table.
	DeleteAll(ctx context.Context) (int64, error)
	ListFiltered(ctx context.Context, f *model.StockZhAListFilters, limit, offset int) ([]*model.StockZhAList, error)
	CountFiltered(ctx context.Context, f *model.StockZhAListFilters) (int64, error)
}

type stockZhAListDaoImpl struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewStockZhAListDao(dsName string) StockZhAListDao {
	return &stockZhAListDaoImpl{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_STOCK_ZH_A_LIST, consts.COMPONENT_LOGGING),
		dsName:        dsName,
	}
}

func (d *stockZhAListDaoImpl) Start(ctx context.Context) error {
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

func (d *stockZhAListDaoImpl) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

func normalizeExchange(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	if len(s) > 2 {
		// keep last compatible behavior as best-effort; callers should pass SH/SZ/BJ
		return s[:2]
	}
	return s
}

func normalizeCode(s string) string {
	return strings.TrimSpace(s)
}

func normalizeCompany(s string) string {
	return strings.TrimSpace(s)
}

func (d *stockZhAListDaoImpl) Create(ctx context.Context, s *model.StockZhAList) error {
	s.Code = normalizeCode(s.Code)
	s.Exchange = normalizeExchange(s.Exchange)
	s.Company = normalizeCompany(s.Company)
	return d.db.WithContext(ctx).Create(s).Error
}

func (d *stockZhAListDaoImpl) BatchUpsert(ctx context.Context, list []*model.StockZhAList, chunkSize int) (int64, error) {
	if len(list) == 0 {
		return 0, nil
	}
	if chunkSize <= 0 {
		chunkSize = 200
	}
	for _, s := range list {
		s.Code = normalizeCode(s.Code)
		s.Exchange = normalizeExchange(s.Exchange)
		s.Company = normalizeCompany(s.Company)
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
				Columns: []clause.Column{{Name: "code"}},
				DoUpdates: clause.Assignments(map[string]any{
					"company":  gorm.Expr("VALUES(company)"),
					"exchange": gorm.Expr("VALUES(exchange)"),
				}),
			}).
			Create(&batch)
		if res.Error != nil {
			logging.Error(ctx, fmt.Sprintf("StockZhAListDaoImpl BatchUpsert: %v", res.Error))
			return affected, res.Error
		}
		affected += res.RowsAffected
	}
	return affected, nil
}

func (d *stockZhAListDaoImpl) Get(ctx context.Context, code string) (*model.StockZhAList, error) {
	code = normalizeCode(code)
	var s model.StockZhAList
	if err := d.db.WithContext(ctx).Where("code=?", code).First(&s).Error; err != nil {
		return nil, err
	}
	return &s, nil
}

func (d *stockZhAListDaoImpl) Update(ctx context.Context, s *model.StockZhAList) error {
	if strings.TrimSpace(s.Code) == "" {
		return fmt.Errorf("update requires code")
	}
	s.Code = normalizeCode(s.Code)
	s.Exchange = normalizeExchange(s.Exchange)
	s.Company = normalizeCompany(s.Company)

	updates := map[string]any{
		"company":  s.Company,
		"exchange": s.Exchange,
	}
	res := d.db.WithContext(ctx).Model(&model.StockZhAList{}).Where("code=?", s.Code).Updates(updates)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *stockZhAListDaoImpl) DeleteAll(ctx context.Context) (int64, error) {
	res := d.db.WithContext(ctx).Exec("DELETE FROM stock_zh_a_list")
	return res.RowsAffected, res.Error
}

func (d *stockZhAListDaoImpl) ListFiltered(ctx context.Context, f *model.StockZhAListFilters, limit, offset int) ([]*model.StockZhAList, error) {
	var list []*model.StockZhAList
	q := d.db.WithContext(ctx).Model(&model.StockZhAList{}).Order("code ASC")
	q = applyStockFilters(q, f)
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

func (d *stockZhAListDaoImpl) CountFiltered(ctx context.Context, f *model.StockZhAListFilters) (int64, error) {
	q := d.db.WithContext(ctx).Model(&model.StockZhAList{})
	q = applyStockFilters(q, f)
	var cnt int64
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}

// applyStockFilters applies common list/count filters.
// Typical usage:
// - exchange exact match (SH/SZ/BJ)
// - code exact match
// - company LIKE match
func applyStockFilters(q *gorm.DB, f *model.StockZhAListFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if strings.TrimSpace(f.Company) != "" {
		q = q.Where("company LIKE ?", "%"+normalizeCompany(f.Company)+"%")
	}
	if len(f.Codes) > 0 {
		if len(f.Codes) > 0 {
			q = q.Where("code IN ?", f.Codes)
		}
	} else if strings.TrimSpace(f.Code) != "" {
		q = q.Where("code=?", normalizeCode(f.Code))
	}
	if strings.TrimSpace(f.Exchange) != "" {
		q = q.Where("exchange=?", normalizeExchange(f.Exchange))
	}
	return q
}
