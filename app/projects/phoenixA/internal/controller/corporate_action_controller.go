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

type CorporateActionController struct {
	*core.BaseComponent
	Svc *service.CorporateActionService `infra:"dep:svc_corp_action"`
}

func NewCorporateActionController() *CorporateActionController {
	return &CorporateActionController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_CORP_ACTION)}
}

func (c *CorporateActionController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}
func (c *CorporateActionController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

// POST /api/v2/corporate-action/{source}/{action_type}/upsert
func (c *CorporateActionController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	actionType := chi.URLParam(r, "action_type")
	if source == "" || actionType == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and action_type are required"})
		return
	}
	var list []*model.CorporateAction
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, item := range list {
		item.Source = source
		item.ActionType = actionType
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

// GET /api/v2/corporate-action/{source}/{action_type}
//
// Query params:
//
//	format          - "nested" (default) | "flat"
//	fields          - comma-separated raw/canonical field names; resolved
//	                  through the field dictionary. Unknown fields return 400
//	                  with suggestions.
//	symbol / symbols / market / report_period / period_start / period_end /
//	ann_date_before / progress_code / page / page_size
func (c *CorporateActionController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	actionType := chi.URLParam(r, "action_type")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))
	format := q.Get("format")
	if format == "" {
		format = "nested"
	}

	f := &model.CorporateActionFilters{
		ActionType:    actionType,
		Symbol:        q.Get("symbol"),
		Market:        q.Get("market"),
		ReportPeriod:  q.Get("report_period"),
		PeriodStart:   q.Get("period_start"),
		PeriodEnd:     q.Get("period_end"),
		AnnDateBefore: q.Get("ann_date_before"),
		ProgressCode:  q.Get("progress_code"),
	}
	var requestedFields []string
	if v := q.Get("fields"); v != "" {
		requestedFields = strings.Split(v, ",")
		f.Fields = requestedFields
	}
	if v := q.Get("symbols"); v != "" {
		f.Symbols = strings.Split(v, ",")
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
