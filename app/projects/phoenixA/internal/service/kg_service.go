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

// KgService handles business logic for the kg (Knowledge Graph) domain.
type KgService struct {
	*core.BaseComponent
	Dao *dao.KgDao `infra:"dep:dao_kg"`
}

func NewKgService() *KgService {
	return &KgService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_KG, consts.COMPONENT_LOGGING),
	}
}

func (s *KgService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_kg is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *KgService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

// ── Documents ─────────────────────────────────────────────────────────────

func (s *KgService) CreateDocument(ctx context.Context, doc *model.KgDocument) error {
	logging.Infof(ctx, "KgService CreateDocument doc_id=%s type=%s", doc.DocID, doc.DocType)
	return s.Dao.CreateDocument(ctx, doc)
}

func (s *KgService) ListDocuments(ctx context.Context, f *model.KgDocumentFilters, limit, offset int) ([]*model.KgDocument, error) {
	return s.Dao.ListDocuments(ctx, f, limit, offset)
}

func (s *KgService) GetDocument(ctx context.Context, docID string) (*model.KgDocument, error) {
	return s.Dao.GetDocument(ctx, docID)
}

func (s *KgService) UpdateDocument(ctx context.Context, docID string, updates map[string]interface{}) error {
	logging.Infof(ctx, "KgService UpdateDocument doc_id=%s", docID)
	return s.Dao.UpdateDocument(ctx, docID, updates)
}

// ── Extractions ───────────────────────────────────────────────────────────

func (s *KgService) CreateExtraction(ctx context.Context, ext *model.KgExtraction) error {
	logging.Infof(ctx, "KgService CreateExtraction doc_id=%s chunk=%d", ext.DocID, ext.ChunkIndex)
	return s.Dao.CreateExtraction(ctx, ext)
}

func (s *KgService) ListExtractions(ctx context.Context, f *model.KgExtractionFilters, limit, offset int) ([]*model.KgExtraction, error) {
	return s.Dao.ListExtractions(ctx, f, limit, offset)
}

func (s *KgService) GetExtraction(ctx context.Context, id int64) (*model.KgExtraction, error) {
	return s.Dao.GetExtraction(ctx, id)
}

// ── Events ────────────────────────────────────────────────────────────────

func (s *KgService) CreateEvent(ctx context.Context, event *model.KgEvent) error {
	logging.Infof(ctx, "KgService CreateEvent fingerprint=%s entity=%s type=%s",
		event.EventFingerprint, event.EntityName, event.EventType)
	return s.Dao.CreateEvent(ctx, event)
}

func (s *KgService) ListEvents(ctx context.Context, f *model.KgEventFilters, limit, offset int) ([]*model.KgEvent, error) {
	return s.Dao.ListEvents(ctx, f, limit, offset)
}

func (s *KgService) GetEvent(ctx context.Context, id int64) (*model.KgEvent, error) {
	return s.Dao.GetEvent(ctx, id)
}

func (s *KgService) GetEventByFingerprint(ctx context.Context, fingerprint string) (*model.KgEvent, error) {
	return s.Dao.GetEventByFingerprint(ctx, fingerprint)
}

func (s *KgService) UpdateEvent(ctx context.Context, id int64, updates map[string]interface{}) error {
	logging.Infof(ctx, "KgService UpdateEvent id=%d", id)
	return s.Dao.UpdateEvent(ctx, id, updates)
}

func (s *KgService) ListRecentEvents(ctx context.Context, days, limit int) ([]*model.KgEvent, error) {
	return s.Dao.ListRecentEvents(ctx, days, limit)
}

// ── Graph Ingestions ──────────────────────────────────────────────────────

func (s *KgService) CreateGraphIngestion(ctx context.Context, gi *model.KgGraphIngestion) error {
	return s.Dao.CreateGraphIngestion(ctx, gi)
}

// ── Daily Runs ────────────────────────────────────────────────────────────

func (s *KgService) CreateDailyRun(ctx context.Context, run *model.KgDailyRun) error {
	logging.Infof(ctx, "KgService CreateDailyRun date=%s", run.RunDate)
	return s.Dao.CreateDailyRun(ctx, run)
}

func (s *KgService) UpdateDailyRun(ctx context.Context, id int64, updates map[string]interface{}) error {
	return s.Dao.UpdateDailyRun(ctx, id, updates)
}

func (s *KgService) ListDailyRuns(ctx context.Context, f *model.KgDailyRunFilters, limit, offset int) ([]*model.KgDailyRun, error) {
	return s.Dao.ListDailyRuns(ctx, f, limit, offset)
}

// ── Impact Logs ───────────────────────────────────────────────────────────

func (s *KgService) CreateImpactLog(ctx context.Context, log *model.KgImpactLog) error {
	logging.Infof(ctx, "KgService CreateImpactLog event=%s", log.EventName)
	return s.Dao.CreateImpactLog(ctx, log)
}

func (s *KgService) ListImpactLogs(ctx context.Context, f *model.KgImpactLogFilters, limit, offset int) ([]*model.KgImpactLog, error) {
	return s.Dao.ListImpactLogs(ctx, f, limit, offset)
}

