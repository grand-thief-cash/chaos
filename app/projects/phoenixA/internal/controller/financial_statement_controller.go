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
	// Enforce source and statement_type from URL
	for _, item := range list {
		item.Source = source
		item.StatementType = stmtType
		if item.Market == "" {
			item.Market = "zh_a"
		}
	}
	if err := c.Svc.BatchUpsert(r.Context(), list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/financial/{source}/{statement_type}
func (c *FinancialStatementController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	stmtType := chi.URLParam(r, "statement_type")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.FinancialStatementFilters{
		StatementType: stmtType,
		Symbol:        q.Get("symbol"),
		Market:        q.Get("market"),
		PeriodStart:   q.Get("period_start"),
		PeriodEnd:     q.Get("period_end"),
		AnnDateBefore: q.Get("ann_date_before"),
		ReportType:    q.Get("report_type"),
	}
	if v := q.Get("fields"); v != "" {
		f.Fields = strings.Split(v, ",")
	}
	if v := q.Get("symbols"); v != "" {
		f.Symbols = strings.Split(v, ",")
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

	list, count, err := c.Svc.Query(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "total": count})
}
