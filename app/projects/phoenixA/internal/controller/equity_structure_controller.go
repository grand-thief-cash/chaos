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

type EquityStructureController struct {
	*core.BaseComponent
	Svc *service.EquityStructureService `infra:"dep:svc_equity_structure"`
}

func NewEquityStructureController() *EquityStructureController {
	return &EquityStructureController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_EQUITY_STRUCTURE)}
}

func (c *EquityStructureController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}
func (c *EquityStructureController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

// POST /api/v2/equity-structure/{source}/upsert
func (c *EquityStructureController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	var list []*model.EquityStructure
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, item := range list {
		item.Source = source
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

// GET /api/v2/equity-structure/{source}
//
// Query params:
//
//	format          - "nested" (default) | "flat"
//	fields          - comma-separated raw/canonical field names; resolved
//	                  through the field dictionary. Unknown fields return 400
//	                  with suggestions.
//	symbol / symbols / market / change_date / change_start / change_end /
//	ann_date_before / current_only / valid_only / page / page_size
func (c *EquityStructureController) Query(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))
	format := q.Get("format")
	if format == "" {
		format = "nested"
	}

	f := &model.EquityStructureFilters{
		Symbol:        q.Get("symbol"),
		Market:        q.Get("market"),
		ChangeDate:    q.Get("change_date"),
		ChangeStart:   q.Get("change_start"),
		ChangeEnd:     q.Get("change_end"),
		AnnDateBefore: q.Get("ann_date_before"),
	}
	if v := q.Get("current_only"); v == "1" || strings.EqualFold(v, "true") {
		f.CurrentOnly = true
	}
	if v := q.Get("valid_only"); v == "1" || strings.EqualFold(v, "true") {
		f.ValidOnly = true
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
