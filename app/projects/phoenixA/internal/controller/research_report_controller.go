package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// Enum sets (defense in depth alongside the DB CHECK constraints).
var (
	validReportTypes = map[string]bool{"stock": true, "industry": true, "other": true}
	validStatuses    = map[string]bool{"pending": true, "downloaded": true, "no_pdf": true, "detail_error": true, "pdf_error": true}
)

// ResearchReportController handles HTTP endpoints for the research-report
// download-state tracker. phoenixA stores ONLY metadata + a MinIO object key
// pointer; PDF bytes live in MinIO (managed by artemis).
type ResearchReportController struct {
	*core.BaseComponent
	Svc *service.ResearchReportService `infra:"dep:svc_research_report"`
}

func NewResearchReportController() *ResearchReportController {
	return &ResearchReportController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_RESEARCH_REPORT)}
}

func (c *ResearchReportController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}
func (c *ResearchReportController) Stop(ctx context.Context) error { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/research-report/{source}/upsert
//
// Request body: JSON array of research-report download records. Each row MUST
// carry source + resource_id (the natural key). security_id is the subject for
// report_type=stock (NULL for industry/other). On conflict, only metadata
// columns are refreshed; the download lifecycle (status/pdf_object_key/...)
// is left untouched.
func (c *ResearchReportController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	var list []*model.ResearchReport
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	// Enforce source from URL + validate report_type (default stock).
	for _, item := range list {
		item.Source = source
		if item.ReportType == "" {
			item.ReportType = "stock"
		}
		// Extra is NOT NULL with jsonb_typeof='object'; default a missing/empty
		// payload to {} so callers that omit extra don't violate the CHECK.
		if len(item.Extra) == 0 {
			item.Extra = json.RawMessage("{}")
		}
		if !validReportTypes[item.ReportType] {
			writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("invalid report_type: %q (want stock|industry|other)", item.ReportType)})
			return
		}
		if (item.ReportType == "stock" || item.ReportType == "industry") && item.SubjectSourceCode == "" {
			writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("subject_source_code required for report_type %q", item.ReportType)})
			return
		}
	}
	if err := c.Svc.BatchUpsertPending(r.Context(), list); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// updateStatusRequest is the body for POST .../{resource_id}/status.
type updateStatusRequest struct {
	Status       string `json:"status"`
	PDFObjectKey string `json:"pdf_object_key"`
	PDFURL       string `json:"pdf_url"`
	LastError    string `json:"last_error"`
}

// POST /api/v2/research-report/{source}/{resource_id}/status
//
// Advances the download lifecycle for a single report. artemis calls this
// after downloading the PDF to MinIO (status=downloaded) or on failure
// (status=detail_error / pdf_error / no_pdf).
func (c *ResearchReportController) UpdateStatus(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	resourceID := chi.URLParam(r, "resource_id")
	if source == "" || resourceID == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and resource_id are required"})
		return
	}
	var body updateStatusRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if body.Status == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "status is required"})
		return
	}
	if !validStatuses[body.Status] {
		writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("invalid status: %q (want pending|downloaded|no_pdf|detail_error|pdf_error)", body.Status)})
		return
	}
	if err := c.Svc.UpdateStatus(r.Context(), source, resourceID, body.Status, body.PDFObjectKey, body.PDFURL, body.LastError); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// GET /api/v2/research-report/{source}/last-update
//
// Returns the MAX(publish_date) among already-downloaded rows for the source,
// or "" when none have been downloaded.
func (c *ResearchReportController) GetLastUpdate(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	last, err := c.Svc.GetLastUpdate(r.Context(), source)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"last_update": last})
}

// GET /api/v2/research-report/{source}/max-publish-date
//
// Returns the MAX(publish_date) across ALL rows for the source (any status),
// or "" when none exist. artemis uses this as the list high-water mark so each
// run lists only new reports.
func (c *ResearchReportController) GetMaxPublishDate(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	last, err := c.Svc.GetMaxPublishDate(r.Context(), source)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"max_publish_date": last})
}

// GET /api/v2/research-report/{source}/pending
//
// Query params: start_date, end_date, limit. Returns rows still awaiting
// download (status in pending/detail_error/pdf_error) within the publish-date
// window, ordered for stable processing. limit defaults to 50; limit<=0 is
// treated as 50 (never returns the full pending set — anti-bot safety).
func (c *ResearchReportController) QueryPending(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	q := r.URL.Query()
	startDate := normalizeDateYYYYMMDD(q.Get("start_date"))
	endDate := normalizeDateYYYYMMDD(q.Get("end_date"))
	limit, _ := strconv.Atoi(q.Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	list, err := c.Svc.QueryPending(r.Context(), source, startDate, endDate, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "count": len(list)})
}

// GET /api/v2/research-report/{source}
//
// General query with pagination. Query params:
// subject_id / subject_ids / resource_id / report_type / status /
// start_date / end_date / page / page_size
func (c *ResearchReportController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.ResearchReportFilters{
		ResourceID:       q.Get("resource_id"),
		ReportType:       q.Get("report_type"),
		Status:           q.Get("status"),
		PublishDateStart: normalizeDateYYYYMMDD(q.Get("start_date")),
		PublishDateEnd:   normalizeDateYYYYMMDD(q.Get("end_date")),
	}
	if q.Has("subject_id") {
		v := q.Get("subject_id")
		id, err := strconv.ParseUint(v, 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid subject_id: must be a positive integer"})
			return
		}
		f.SubjectID = id
	}
	if q.Has("subject_ids") {
		ids, err := parseUint64ListStrict(q.Get("subject_ids"))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
			return
		}
		f.SubjectIDs = ids
	}

	list, count, err := c.Svc.Query(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "total": count})
}
