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

// ResearchReportDao handles persistence for the research-report download-state
// tracker (table ods.research_report_download_record). Scoped to download-task
// needs only — no research-report business content columns.
type ResearchReportDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewResearchReportDao(dsName string) *ResearchReportDao {
	return &ResearchReportDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_RESEARCH_REPORT),
		dsName:        dsName,
	}
}

func (d *ResearchReportDao) Start(ctx context.Context) error {
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

func (d *ResearchReportDao) Stop(ctx context.Context) error {
	return d.BaseComponent.Stop(ctx)
}

// BatchUpsertPending upserts research-report download records. The unique key
// is (source, resource_id). On conflict, ONLY metadata columns are refreshed —
// status, pdf_object_key, pdf_url, last_error and updated_at are deliberately
// left untouched so an already-downloaded row stays downloaded (artemis
// re-scraping the listing must not reset the download lifecycle).
func (d *ResearchReportDao) BatchUpsertPending(ctx context.Context, list []*model.ResearchReport) error {
	if len(list) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns: []clause.Column{
				{Name: "source"}, {Name: "resource_id"},
			},
			DoUpdates: clause.AssignmentColumns([]string{
				"report_type", "subject_id", "subject_source_code", "publish_date",
				"title", "org_name", "detail_url",
			}),
		}).CreateInBatches(list, 200).Error
}

// UpdateStatus advances the download lifecycle for a single report: sets
// status, pdf_object_key, pdf_url, last_error and bumps updated_at=NOW().
func (d *ResearchReportDao) UpdateStatus(ctx context.Context, source, resourceID, status, pdfObjectKey, pdfURL, lastError string) error {
	return d.db.WithContext(ctx).
		Model(&model.ResearchReport{}).
		Where("source = ? AND resource_id = ?", source, resourceID).
		Updates(map[string]any{
			"status":         status,
			"pdf_object_key": pdfObjectKey,
			"pdf_url":        pdfURL,
			"last_error":     lastError,
			"updated_at":     gorm.Expr("NOW()"),
		}).Error
}

// GetLastUpdate returns the MAX(publish_date) among already-downloaded rows
// for the given source, or "" when no downloaded rows exist. (Reporting /
// "how far downloaded" indicator.)
func (d *ResearchReportDao) GetLastUpdate(ctx context.Context, source string) (string, error) {
	var last string
	err := d.db.WithContext(ctx).
		Model(&model.ResearchReport{}).
		Where("source = ? AND status = ?", source, "downloaded").
		Select("COALESCE(MAX(publish_date), '')").
		Row().Scan(&last)
	if err != nil {
		return "", err
	}
	return last, nil
}

// GetMaxPublishDate returns the MAX(publish_date) across ALL rows for the
// source (any status), or "" when none exist. artemis uses this as the list
// high-water mark so each run lists only new reports.
func (d *ResearchReportDao) GetMaxPublishDate(ctx context.Context, source string) (string, error) {
	var last string
	err := d.db.WithContext(ctx).
		Model(&model.ResearchReport{}).
		Where("source = ?", source).
		Select("COALESCE(MAX(publish_date), '')").
		Row().Scan(&last)
	if err != nil {
		return "", err
	}
	return last, nil
}

// QueryPending returns rows still awaiting download (status in
// pending/detail_error/pdf_error) within the [startDate, endDate] publish-date
// window, ordered for stable processing. limit<=0 yields no rows (safety: a
// missing/zero/negative limit must NOT return the entire pending set, which
// would risk a runaway full-download under eastmoney anti-bot pacing).
func (d *ResearchReportDao) QueryPending(ctx context.Context, source, startDate, endDate string, limit int) ([]*model.ResearchReport, error) {
	if limit <= 0 {
		return []*model.ResearchReport{}, nil
	}
	var list []*model.ResearchReport
	q := d.db.WithContext(ctx).
		Model(&model.ResearchReport{}).
		Where("source = ?", source).
		Where("status IN ?", []string{"pending", "detail_error", "pdf_error"})
	if startDate != "" {
		q = q.Where("publish_date >= ?", startDate)
	}
	if endDate != "" {
		q = q.Where("publish_date <= ?", endDate)
	}
	q = q.Order("publish_date ASC, id ASC").Limit(limit)
	if err := q.Find(&list).Error; err != nil {
		return nil, err
	}
	return list, nil
}

// Query returns research-report download records matching the given filters.
func (d *ResearchReportDao) Query(ctx context.Context, source string, f *model.ResearchReportFilters, limit, offset int) ([]*model.ResearchReport, error) {
	var list []*model.ResearchReport
	q := d.db.WithContext(ctx).Model(&model.ResearchReport{}).
		Where("source = ?", source).
		Order("publish_date DESC, id ASC")

	if f != nil && len(f.Fields) > 0 {
		q = q.Select(f.Fields)
	}

	if f != nil {
		if f.SubjectID != 0 {
			q = q.Where("subject_id = ?", f.SubjectID)
		}
		if len(f.SubjectIDs) > 0 {
			q = q.Where("subject_id IN ?", f.SubjectIDs)
		}
		if f.ResourceID != "" {
			q = q.Where("resource_id = ?", f.ResourceID)
		}
		if f.ReportType != "" {
			q = q.Where("report_type = ?", f.ReportType)
		}
		if f.Status != "" {
			q = q.Where("status = ?", f.Status)
		}
		if f.PublishDateStart != "" {
			q = q.Where("publish_date >= ?", f.PublishDateStart)
		}
		if f.PublishDateEnd != "" {
			q = q.Where("publish_date <= ?", f.PublishDateEnd)
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

// Count returns the count of research-report download records matching the given filters.
func (d *ResearchReportDao) Count(ctx context.Context, source string, f *model.ResearchReportFilters) (int64, error) {
	var cnt int64
	q := d.db.WithContext(ctx).Model(&model.ResearchReport{}).Where("source = ?", source)
	if f != nil {
		if f.SubjectID != 0 {
			q = q.Where("subject_id = ?", f.SubjectID)
		}
		if len(f.SubjectIDs) > 0 {
			q = q.Where("subject_id IN ?", f.SubjectIDs)
		}
		if f.ResourceID != "" {
			q = q.Where("resource_id = ?", f.ResourceID)
		}
		if f.ReportType != "" {
			q = q.Where("report_type = ?", f.ReportType)
		}
		if f.Status != "" {
			q = q.Where("status = ?", f.Status)
		}
		if f.PublishDateStart != "" {
			q = q.Where("publish_date >= ?", f.PublishDateStart)
		}
		if f.PublishDateEnd != "" {
			q = q.Where("publish_date <= ?", f.PublishDateEnd)
		}
	}
	if err := q.Count(&cnt).Error; err != nil {
		return 0, err
	}
	return cnt, nil
}
