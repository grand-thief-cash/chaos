package controller

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"gorm.io/gorm"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// KgController handles HTTP endpoints for the kg (Knowledge Graph) domain.
type KgController struct {
	*core.BaseComponent
	Svc *service.KgService `infra:"dep:svc_kg"`
}

func NewKgController() *KgController {
	return &KgController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_KG)}
}

func (c *KgController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *KgController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// ── Documents ─────────────────────────────────────────────────────────────

// POST /api/v1/kg/documents
func (c *KgController) CreateDocument(w http.ResponseWriter, r *http.Request) {
	var doc model.KgDocument
	if err := json.NewDecoder(r.Body).Decode(&doc); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if doc.DocID == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "doc_id is required"})
		return
	}
	if err := c.Svc.CreateDocument(r.Context(), &doc); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: doc})
}

// GET /api/v1/kg/documents
func (c *KgController) ListDocuments(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 50
	}
	q := r.URL.Query()
	f := &model.KgDocumentFilters{
		DocType:    q.Get("doc_type"),
		SourceType: q.Get("source_type"),
		Company:    q.Get("company"),
	}
	if q.Get("processed") != "" {
		val := q.Get("processed") == "true"
		f.Processed = &val
	}
	list, err := c.Svc.ListDocuments(r.Context(), f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// GET /api/v1/kg/documents/{doc_id}
func (c *KgController) GetDocument(w http.ResponseWriter, r *http.Request, docID string) {
	doc, err := c.Svc.GetDocument(r.Context(), docID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "document not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: doc})
}

// PUT /api/v1/kg/documents/{doc_id}
func (c *KgController) UpdateDocument(w http.ResponseWriter, r *http.Request, docID string) {
	var updates map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if err := c.Svc.UpdateDocument(r.Context(), docID, updates); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]string{"status": "updated"}})
}

// ── Extractions ───────────────────────────────────────────────────────────

// POST /api/v1/kg/extractions
func (c *KgController) CreateExtraction(w http.ResponseWriter, r *http.Request) {
	var ext model.KgExtraction
	if err := json.NewDecoder(r.Body).Decode(&ext); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if err := c.Svc.CreateExtraction(r.Context(), &ext); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: ext})
}

// GET /api/v1/kg/extractions
func (c *KgController) ListExtractions(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 50
	}
	q := r.URL.Query()
	f := &model.KgExtractionFilters{
		DocID:         q.Get("doc_id"),
		PromptVersion: q.Get("prompt_version"),
		Status:        q.Get("status"),
	}
	list, err := c.Svc.ListExtractions(r.Context(), f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// GET /api/v1/kg/extractions/{id}
func (c *KgController) GetExtraction(w http.ResponseWriter, r *http.Request, idStr string) {
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid id"})
		return
	}
	ext, err := c.Svc.GetExtraction(r.Context(), id)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "extraction not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: ext})
}

// ── Events ────────────────────────────────────────────────────────────────

// POST /api/v1/kg/events
func (c *KgController) CreateEvent(w http.ResponseWriter, r *http.Request) {
	var event model.KgEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if err := c.Svc.CreateEvent(r.Context(), &event); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: event})
}

// GET /api/v1/kg/events
func (c *KgController) ListEvents(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 50
	}
	q := r.URL.Query()
	f := &model.KgEventFilters{
		Fingerprint: q.Get("fingerprint"),
		EventType:   q.Get("event_type"),
		EntityName:  q.Get("entity_name"),
		TimeBucket:  q.Get("time_bucket"),
		StartTime:   q.Get("start_time"),
		EndTime:     q.Get("end_time"),
	}
	list, err := c.Svc.ListEvents(r.Context(), f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// GET /api/v1/kg/events/{id}
func (c *KgController) GetEvent(w http.ResponseWriter, r *http.Request, idStr string) {
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid id"})
		return
	}
	event, err := c.Svc.GetEvent(r.Context(), id)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "event not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: event})
}

// PUT /api/v1/kg/events/{id}
func (c *KgController) UpdateEvent(w http.ResponseWriter, r *http.Request, idStr string) {
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid id"})
		return
	}
	var updates map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if err := c.Svc.UpdateEvent(r.Context(), id, updates); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]string{"status": "updated"}})
}

// GET /api/v1/kg/events/recent
func (c *KgController) ListRecentEvents(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	days := 7
	if d := q.Get("days"); d != "" {
		if v, err := strconv.Atoi(d); err == nil && v > 0 {
			days = v
		}
	}
	limit := 50
	if l := q.Get("limit"); l != "" {
		if v, err := strconv.Atoi(l); err == nil && v > 0 {
			limit = v
		}
	}
	list, err := c.Svc.ListRecentEvents(r.Context(), days, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// ── Graph Ingestions ──────────────────────────────────────────────────────

// POST /api/v1/kg/graph-ingestions
func (c *KgController) CreateGraphIngestion(w http.ResponseWriter, r *http.Request) {
	var gi model.KgGraphIngestion
	if err := json.NewDecoder(r.Body).Decode(&gi); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if err := c.Svc.CreateGraphIngestion(r.Context(), &gi); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: gi})
}

// ── Daily Runs ────────────────────────────────────────────────────────────

// POST /api/v1/kg/daily-runs
func (c *KgController) CreateDailyRun(w http.ResponseWriter, r *http.Request) {
	var run model.KgDailyRun
	if err := json.NewDecoder(r.Body).Decode(&run); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if err := c.Svc.CreateDailyRun(r.Context(), &run); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: run})
}

// GET /api/v1/kg/daily-runs
func (c *KgController) ListDailyRuns(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 30
	}
	q := r.URL.Query()
	f := &model.KgDailyRunFilters{
		StartDate: q.Get("start_date"),
		EndDate:   q.Get("end_date"),
		Status:    q.Get("status"),
	}
	list, err := c.Svc.ListDailyRuns(r.Context(), f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// ── Impact Logs ───────────────────────────────────────────────────────────

// POST /api/v1/kg/impact-logs
func (c *KgController) CreateImpactLog(w http.ResponseWriter, r *http.Request) {
	var log model.KgImpactLog
	if err := json.NewDecoder(r.Body).Decode(&log); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json: " + err.Error()})
		return
	}
	if err := c.Svc.CreateImpactLog(r.Context(), &log); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, apiResponse[any]{Data: log})
}

// GET /api/v1/kg/impact-logs
func (c *KgController) ListImpactLogs(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 50
	}
	q := r.URL.Query()
	f := &model.KgImpactLogFilters{
		EventName: q.Get("event_name"),
		StartTime: q.Get("start_time"),
		EndTime:   q.Get("end_time"),
	}
	if eid := q.Get("event_id"); eid != "" {
		if v, err := strconv.ParseInt(eid, 10, 64); err == nil {
			f.EventID = &v
		}
	}
	list, err := c.Svc.ListImpactLogs(r.Context(), f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

