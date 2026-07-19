package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// ResearchReportService handles business logic for research-report metadata.
// phoenixA stores ONLY metadata + a MinIO object key pointer; the PDF bytes
// live in MinIO (managed by artemis), never in this service.
type ResearchReportService struct {
	*core.BaseComponent
	Dao     *dao.ResearchReportDao `infra:"dep:dao_research_report"`
	Resolve *ResolveCache          `infra:"dep:svc_resolve_cache?"` // optional — orphan defense for non-null security_id rows
}

func NewResearchReportService() *ResearchReportService {
	return &ResearchReportService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_RESEARCH_REPORT, consts.COMPONENT_LOGGING),
	}
}

func (s *ResearchReportService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_research_report is nil")
	}
	// Resolve is optional: research reports about unregistered stocks (null
	// security_id) are still stored; when present, it validates non-null ids.
	return s.BaseComponent.Start(ctx)
}

func (s *ResearchReportService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

// BatchUpsertPending upserts research-report metadata. When ResolveCache is
// available, stock reports (report_type=stock) have their subject_id validated
// against security_registry (orphan defense, refactor §6 R9 / §10.c) — for
// stock, subject_id IS the security_id. Industry/other report types skip
// security-registry validation (their subject_id lives in a different table).
func (s *ResearchReportService) BatchUpsertPending(ctx context.Context, list []*model.ResearchReport) error {
	if len(list) == 0 {
		return nil
	}
	if s.Resolve != nil {
		ids := make([]uint64, 0, len(list))
		for _, item := range list {
			if item.ReportType == "stock" && item.SubjectID != nil && *item.SubjectID != 0 {
				ids = append(ids, *item.SubjectID)
			}
		}
		if len(ids) > 0 {
			if err := s.Resolve.ValidateSecurityIDsExist(ctx, ids); err != nil {
				return err
			}
		}
	}
	logging.Infof(ctx, "ResearchReportService BatchUpsertPending count=%d", len(list))
	return s.Dao.BatchUpsertPending(ctx, list)
}

// UpdateStatus advances the download lifecycle for a single report.
func (s *ResearchReportService) UpdateStatus(ctx context.Context, source, resourceID, status, pdfObjectKey, pdfURL, lastError string) error {
	return s.Dao.UpdateStatus(ctx, source, resourceID, status, pdfObjectKey, pdfURL, lastError)
}

// GetLastUpdate returns the MAX(publish_date) among downloaded rows for a
// source, or "" when none have been downloaded.
func (s *ResearchReportService) GetLastUpdate(ctx context.Context, source string) (string, error) {
	return s.Dao.GetLastUpdate(ctx, source)
}

// GetMaxPublishDate returns the MAX(publish_date) across ALL rows for a source
// (any status), or "" when none exist. artemis uses this as the list
// high-water mark so each run lists only new reports.
func (s *ResearchReportService) GetMaxPublishDate(ctx context.Context, source string) (string, error) {
	return s.Dao.GetMaxPublishDate(ctx, source)
}

// QueryPending returns rows still awaiting download within the publish-date window.
func (s *ResearchReportService) QueryPending(ctx context.Context, source, startDate, endDate string, limit int) ([]*model.ResearchReport, error) {
	return s.Dao.QueryPending(ctx, source, startDate, endDate, limit)
}

// Query returns research reports matching the given filters with pagination.
func (s *ResearchReportService) Query(ctx context.Context, source string, f *model.ResearchReportFilters, page, pageSize int) ([]*model.ResearchReport, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	if pageSize > 1000 {
		pageSize = 1000
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.Query(ctx, source, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.Count(ctx, source, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}
