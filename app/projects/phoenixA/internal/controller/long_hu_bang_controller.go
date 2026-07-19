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

type LongHuBangController struct {
	*core.BaseComponent
	Svc *service.LongHuBangService `infra:"dep:svc_long_hu_bang"`
}

func NewLongHuBangController() *LongHuBangController {
	return &LongHuBangController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_LONG_HU_BANG)}
}

func (c *LongHuBangController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *LongHuBangController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/long-hu-bang/{source}/upsert
//
// Request body: JSON array of long-hu-bang rows. Each row MUST carry a
// security_id resolved from security_registry; rows with a missing/unknown
// security_id are rejected with 400 (orphan defense, refactor §10.c).
func (c *LongHuBangController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	var list []*model.LongHuBang
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, item := range list {
		item.Source = source
		item.TradeDate = normalizeDateYYYYMMDD(item.TradeDate)
		item.ReasonType = strings.TrimSpace(item.ReasonType)
		item.TraderName = strings.TrimSpace(item.TraderName)
		item.SecurityName = strings.TrimSpace(item.SecurityName)
		item.ReasonTypeName = strings.TrimSpace(item.ReasonTypeName)
	}
	if err := c.Svc.BatchUpsert(r.Context(), list); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/long-hu-bang/{source}
func (c *LongHuBangController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.LongHuBangFilters{
		TradeDate:  normalizeDateYYYYMMDD(q.Get("trade_date")),
		StartDate:  normalizeDateYYYYMMDD(q.Get("start_date")),
		EndDate:    normalizeDateYYYYMMDD(q.Get("end_date")),
		ReasonType: q.Get("reason_type"),
		TraderName: q.Get("trader_name"),
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
	if v := q.Get("fields"); v != "" {
		f.Fields = strings.Split(v, ",")
	}
	if v := q.Get("flow_mark"); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			f.FlowMark = &i
		}
	}

	list, count, err := c.Svc.Query(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "total": count})
}
