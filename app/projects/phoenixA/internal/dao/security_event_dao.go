package dao

import (
	"context"
	"fmt"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type SecurityEventDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewSecurityEventDao(dsName string) *SecurityEventDao {
	return &SecurityEventDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_SECURITY_EVENT),
		dsName:        dsName,
	}
}

func (d *SecurityEventDao) Start(ctx context.Context) error {
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
func (d *SecurityEventDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

func (d *SecurityEventDao) BatchUpsert(ctx context.Context, rows []*model.SecurityEvent) error {
	if len(rows) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{
			{Name: "security_id"}, {Name: "source"}, {Name: "event_type"},
			{Name: "event_date"}, {Name: "title"},
		},
		DoUpdates: clause.AssignmentColumns([]string{"url", "data_json"}),
	}).CreateInBatches(rows, 500).Error
}

func (d *SecurityEventDao) Query(
	ctx context.Context, source, eventType string, f *model.SecurityEventFilters, limit, offset int,
) ([]*model.SecurityEvent, error) {
	var rows []*model.SecurityEvent
	q := d.db.WithContext(ctx).Model(&model.SecurityEvent{}).
		Where("source = ? AND event_type = ?", source, eventType).
		Order("event_date DESC, security_id ASC")
	if f.SecurityID != 0 {
		q = q.Where("security_id = ?", f.SecurityID)
	}
	if len(f.SecurityIDs) > 0 {
		q = q.Where("security_id IN ?", f.SecurityIDs)
	}
	if f.StartDate != "" {
		q = q.Where("event_date >= ?", f.StartDate)
	}
	if f.EndDate != "" {
		q = q.Where("event_date <= ?", f.EndDate)
	}
	if f.Title != "" {
		q = q.Where("title = ?", f.Title)
	}
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	return rows, q.Find(&rows).Error
}

func (d *SecurityEventDao) LastDatesBySecurityIDs(
	ctx context.Context,
	source, eventType string,
	securityIDs []uint64,
) ([]*model.SecurityEventLastUpdate, error) {
	rows := make([]*model.SecurityEventLastUpdate, 0)
	q := d.db.WithContext(ctx).Model(&model.SecurityEvent{}).
		Select("security_id, MAX(event_date)::text AS last_update").
		Where("source = ? AND event_type = ?", source, eventType).
		Group("security_id").
		Order("security_id ASC")
	if len(securityIDs) > 0 {
		q = q.Where("security_id IN ?", securityIDs)
	}
	return rows, q.Scan(&rows).Error
}
