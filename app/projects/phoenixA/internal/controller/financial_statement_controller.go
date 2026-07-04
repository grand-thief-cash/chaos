package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// FinancialStatementController handles HTTP endpoints for financial statement data.
type FinancialStatementController struct {
	*core.BaseComponent
	Svc *service.FinancialStatementService `infra:"dep:svc_financial_stmt"`
}

func NewFinancialStatementController() *FinancialStatementController {
	return &FinancialStatementController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_FINANCIAL_STMT)}
}

func (c *FinancialStatementController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}
func (c *FinancialStatementController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

// POST /api/v2/financial/{source}/{statement_type}/upsert
//
// Request body: JSON array of financial-statement rows. Each row MUST carry a
// security_id resolved from security_registry; rows with a missing/unknown
// security_id are rejected with 400 (orphan defense, refactor §10.c).
func (c *FinancialStatementController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	stmtType := chi.URLParam(r, "statement_type")
	if source == "" || stmtType == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and statement_type are required"})
		return
	}
	var list []*model.FinancialStatement
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	// Enforce source and statement_type from URL.
	for _, item := range list {
		item.Source = source
		item.StatementType = stmtType
	}
	if err := c.Svc.BatchUpsert(r.Context(), list); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/financial/{source}/{statement_type}
//
// Query params:
//
//	format          - "nested" (default) | "flat"
//	fields          - comma-separated raw/canonical field names; resolved
//	                  through the field dictionary. Unknown fields return 400
//	                  with suggestions.
//	security_id / security_ids / period_start / period_end / reporting_period /
//	reporting_periods / ann_date_before / report_type / statement_code /
//	comp_type_code / page / page_size
func (c *FinancialStatementController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	stmtType := chi.URLParam(r, "statement_type")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))
	format := q.Get("format")
	if format == "" {
		format = "nested"
	}

	f := &model.FinancialStatementFilters{
		StatementType: stmtType,
		StatementCode: q.Get("statement_code"),
		PeriodStart:   q.Get("period_start"),
		PeriodEnd:     q.Get("period_end"),
		AnnDateBefore: q.Get("ann_date_before"),
		ReportType:    q.Get("report_type"),
	}
	if q.Has("security_id") {
		v := q.Get("security_id")
		id, err := strconv.ParseUint(v, 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id: must be a positive integer"})
			return
		}
		f.SecurityID = id
	}
	if q.Has("security_ids") {
		ids, err := parseUint64ListStrict(q.Get("security_ids"))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
			return
		}
		f.SecurityIDs = ids
	}
	var requestedFields []string
	if v := q.Get("fields"); v != "" {
		requestedFields = strings.Split(v, ",")
		f.Fields = requestedFields
	}
	if v := q.Get("reporting_period"); v != "" {
		f.ReportingPeriod = v
	}
	if v := q.Get("reporting_periods"); v != "" {
		f.ReportingPeriods = strings.Split(v, ",")
	}
	if v := q.Get("comp_type_code"); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			f.CompTypeCode = &i
		}
	}

	switch format {
	case "flat":
		resp, err := c.Svc.QueryFlat(r.Context(), source, f, requestedFields, page, pageSize)
		if err != nil {
			writeQueryError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	case "nested":
		resp, err := c.Svc.QueryNested(r.Context(), source, f, requestedFields, page, pageSize)
		if err != nil {
			writeQueryError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	default:
		writeJSON(w, http.StatusBadRequest, apiError{Error: "format must be 'flat' or 'nested'"})
	}
}
