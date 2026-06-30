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

type AdjustFactorController struct {
	*core.BaseComponent
	Svc *service.AdjustFactorService `infra:"dep:svc_adjust_factor"`
}

func NewAdjustFactorController() *AdjustFactorController {
	return &AdjustFactorController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_ADJUST_FACTOR)}
}

func (c *AdjustFactorController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *AdjustFactorController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/adjust-factors/{source}/upsert
func (c *AdjustFactorController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	var list []*model.AdjustFactor
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, item := range list {
		item.Source = source
		if item.Market == "" {
			item.Market = "zh_a"
		}
		item.DividOperateDate = normalizeDateYYYYMMDD(item.DividOperateDate)
	}
	if err := c.Svc.BatchUpsert(r.Context(), list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/adjust-factors/{source}
func (c *AdjustFactorController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.AdjustFactorFilters{
		Symbol:    q.Get("symbol"),
		Market:    q.Get("market"),
		StartDate: normalizeDateYYYYMMDD(q.Get("start_date")),
		EndDate:   normalizeDateYYYYMMDD(q.Get("end_date")),
	}
	if v := q.Get("fields"); v != "" {
		f.Fields = strings.Split(v, ",")
	}
	if v := q.Get("symbols"); v != "" {
		f.Symbols = strings.Split(v, ",")
	}

	list, count, err := c.Svc.Query(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "total": count})
}
