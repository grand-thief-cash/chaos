package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"

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
func (c *CorporateActionController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	actionType := chi.URLParam(r, "action_type")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.CorporateActionFilters{
		ActionType:   actionType,
		Symbol:       q.Get("symbol"),
		Market:       q.Get("market"),
		ReportPeriod: q.Get("report_period"),
		PeriodStart:  q.Get("period_start"),
		PeriodEnd:    q.Get("period_end"),
		ProgressCode: q.Get("progress_code"),
	}

	list, count, err := c.Svc.Query(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "total": count})
}
