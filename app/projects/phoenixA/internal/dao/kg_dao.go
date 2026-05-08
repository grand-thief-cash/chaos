package dao

import (
	"context"
	"fmt"
	"strings"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
)

// KgDao handles all CRUD operations for the kg schema tables.
type KgDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewKgDao(dsName string) *KgDao {
	return &KgDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_KG),
		dsName:        dsName,
	}
}

func (d *KgDao) Start(ctx context.Context) error {
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

func (d *KgDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// ── Documents ─────────────────────────────────────────────────────────────

func (d *KgDao) CreateDocument(ctx context.Context, doc *model.KgDocument) error {
	return d.db.WithContext(ctx).Create(doc).Error
}

func (d *KgDao) ListDocuments(ctx context.Context, f *model.KgDocumentFilters, limit, offset int) ([]*model.KgDocument, error) {
	var list []*model.KgDocument
	q := d.db.WithContext(ctx).Model(&model.KgDocument{}).Order("created_at DESC")
	q = applyKgDocFilters(q, f)
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

func (d *KgDao) GetDocument(ctx context.Context, docID string) (*model.KgDocument, error) {
	var doc model.KgDocument
	if err := d.db.WithContext(ctx).Where("doc_id = ?", docID).First(&doc).Error; err != nil {
		return nil, err
	}
	return &doc, nil
}

func (d *KgDao) UpdateDocument(ctx context.Context, docID string, updates map[string]interface{}) error {
	return d.db.WithContext(ctx).Model(&model.KgDocument{}).Where("doc_id = ?", docID).Updates(updates).Error
}

func applyKgDocFilters(q *gorm.DB, f *model.KgDocumentFilters) *gorm.DB {
	if f == nil {
		return q
	}
	if f.DocType != "" {
		q = q.Where("doc_type = ?", f.DocType)
	}
	if f.SourceType != "" {
		q = q.Where("source_type = ?", f.SourceType)
	}
	if f.Company != "" {
		q = q.Where("company ILIKE ?", "%"+strings.TrimSpace(f.Company)+"%")
	}
	if f.Processed != nil {
		q = q.Where("processed = ?", *f.Processed)
	}
	if f.ContentHash != "" {
		q = q.Where("content_hash = ?", f.ContentHash)
	}
	return q
}

// ── Extractions ───────────────────────────────────────────────────────────

func (d *KgDao) CreateExtraction(ctx context.Context, ext *model.KgExtraction) error {
	return d.db.WithContext(ctx).Create(ext).Error
}

func (d *KgDao) ListExtractions(ctx context.Context, f *model.KgExtractionFilters, limit, offset int) ([]*model.KgExtraction, error) {
	var list []*model.KgExtraction
	q := d.db.WithContext(ctx).Model(&model.KgExtraction{}).Order("created_at DESC")
	if f != nil {
		if f.DocID != "" {
			q = q.Where("doc_id = ?", f.DocID)
		}
		if f.PromptVersion != "" {
			q = q.Where("prompt_version = ?", f.PromptVersion)
		}
		if f.Status != "" {
			q = q.Where("status = ?", f.Status)
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

func (d *KgDao) GetExtraction(ctx context.Context, id int64) (*model.KgExtraction, error) {
	var ext model.KgExtraction
	if err := d.db.WithContext(ctx).First(&ext, id).Error; err != nil {
		return nil, err
	}
	return &ext, nil
}

// ── Events ────────────────────────────────────────────────────────────────

func (d *KgDao) CreateEvent(ctx context.Context, event *model.KgEvent) error {
	return d.db.WithContext(ctx).Create(event).Error
}

func (d *KgDao) ListEvents(ctx context.Context, f *model.KgEventFilters, limit, offset int) ([]*model.KgEvent, error) {
	var list []*model.KgEvent
	q := d.db.WithContext(ctx).Model(&model.KgEvent{}).Order("first_seen_at DESC")
	if f != nil {
		if f.Fingerprint != "" {
			q = q.Where("event_fingerprint = ?", f.Fingerprint)
		}
		if f.EventType != "" {
			q = q.Where("event_type = ?", f.EventType)
		}
		if f.EntityName != "" {
			q = q.Where("entity_name ILIKE ?", "%"+strings.TrimSpace(f.EntityName)+"%")
		}
		if f.TimeBucket != "" {
			q = q.Where("time_bucket = ?", f.TimeBucket)
		}
		if f.StartTime != "" {
			q = q.Where("first_seen_at >= ?", f.StartTime)
		}
		if f.EndTime != "" {
			q = q.Where("first_seen_at <= ?", f.EndTime)
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

func (d *KgDao) GetEvent(ctx context.Context, id int64) (*model.KgEvent, error) {
	var event model.KgEvent
	if err := d.db.WithContext(ctx).First(&event, id).Error; err != nil {
		return nil, err
	}
	return &event, nil
}

func (d *KgDao) GetEventByFingerprint(ctx context.Context, fingerprint string) (*model.KgEvent, error) {
	var event model.KgEvent
	if err := d.db.WithContext(ctx).Where("event_fingerprint = ?", fingerprint).First(&event).Error; err != nil {
		return nil, err
	}
	return &event, nil
}

func (d *KgDao) UpdateEvent(ctx context.Context, id int64, updates map[string]interface{}) error {
	return d.db.WithContext(ctx).Model(&model.KgEvent{}).Where("id = ?", id).Updates(updates).Error
}

func (d *KgDao) ListRecentEvents(ctx context.Context, days int, limit int) ([]*model.KgEvent, error) {
	var list []*model.KgEvent
	q := d.db.WithContext(ctx).Model(&model.KgEvent{}).
		Where("first_seen_at >= NOW() - INTERVAL '1 day' * ?", days).
		Order("first_seen_at DESC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

// ── Graph Ingestions ──────────────────────────────────────────────────────

func (d *KgDao) CreateGraphIngestion(ctx context.Context, gi *model.KgGraphIngestion) error {
	return d.db.WithContext(ctx).Create(gi).Error
}

// ── Daily Runs ────────────────────────────────────────────────────────────

func (d *KgDao) CreateDailyRun(ctx context.Context, run *model.KgDailyRun) error {
	return d.db.WithContext(ctx).Create(run).Error
}

func (d *KgDao) UpdateDailyRun(ctx context.Context, id int64, updates map[string]interface{}) error {
	return d.db.WithContext(ctx).Model(&model.KgDailyRun{}).Where("id = ?", id).Updates(updates).Error
}

func (d *KgDao) ListDailyRuns(ctx context.Context, f *model.KgDailyRunFilters, limit, offset int) ([]*model.KgDailyRun, error) {
	var list []*model.KgDailyRun
	q := d.db.WithContext(ctx).Model(&model.KgDailyRun{}).Order("run_date DESC")
	if f != nil {
		if f.StartDate != "" {
			q = q.Where("run_date >= ?", f.StartDate)
		}
		if f.EndDate != "" {
			q = q.Where("run_date <= ?", f.EndDate)
		}
		if f.Status != "" {
			q = q.Where("status = ?", f.Status)
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

// ── Impact Logs ───────────────────────────────────────────────────────────

func (d *KgDao) CreateImpactLog(ctx context.Context, log *model.KgImpactLog) error {
	return d.db.WithContext(ctx).Create(log).Error
}

func (d *KgDao) ListImpactLogs(ctx context.Context, f *model.KgImpactLogFilters, limit, offset int) ([]*model.KgImpactLog, error) {
	var list []*model.KgImpactLog
	q := d.db.WithContext(ctx).Model(&model.KgImpactLog{}).Order("created_at DESC")
	if f != nil {
		if f.EventID != nil {
			q = q.Where("event_id = ?", *f.EventID)
		}
		if f.EventName != "" {
			q = q.Where("event_name ILIKE ?", "%"+strings.TrimSpace(f.EventName)+"%")
		}
		if f.StartTime != "" {
			q = q.Where("created_at >= ?", f.StartTime)
		}
		if f.EndTime != "" {
			q = q.Where("created_at <= ?", f.EndTime)
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

