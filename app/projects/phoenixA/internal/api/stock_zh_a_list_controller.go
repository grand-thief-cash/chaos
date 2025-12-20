package api

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

type StockZhAListController struct {
	*core.BaseComponent
	Svc *service.StockZhAListService `infra:"dep:stock_zh_a_list_service"`
}

func NewStockZhAListController() *StockZhAListController {
	return &StockZhAListController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_STOCK_ZH_A_LIST)}
}

func (c *StockZhAListController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *StockZhAListController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// ---- helpers ----

type apiError struct {
	Error string `json:"error"`
}

type apiResponse[T any] struct {
	Data T `json:"data"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func parseLimitOffset(r *http.Request) (limit, offset int) {
	q := r.URL.Query()
	if s := q.Get("limit"); s != "" {
		if v, err := strconv.Atoi(s); err == nil {
			limit = v
		}
	}
	if s := q.Get("offset"); s != "" {
		if v, err := strconv.Atoi(s); err == nil {
			offset = v
		}
	}
	return
}

// ---- handlers ----

// GET /api/v1/stocks
func (c *StockZhAListController) list(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	limit, offset := parseLimitOffset(r)
	f := &model.StockZhAListFilters{
		Exchange: r.URL.Query().Get("exchange"),
		Code:     r.URL.Query().Get("code"),
		Company:  r.URL.Query().Get("company"),
	}
	list, err := c.Svc.ListFiltered(ctx, f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// GET /api/v1/stocks/{code}
func (c *StockZhAListController) get(w http.ResponseWriter, r *http.Request, code string) {
	ctx := r.Context()
	s, err := c.Svc.Get(ctx, code)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: s})
}

// POST /api/v1/stocks
func (c *StockZhAListController) create(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req model.StockZhAList
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if err := c.Svc.Create(ctx, &req); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: "ok"})
}

// PUT/PATCH /api/v1/stocks/{code}
func (c *StockZhAListController) update(w http.ResponseWriter, r *http.Request, code string) {
	ctx := r.Context()
	var req model.StockZhAList
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	// path param wins
	req.Code = code
	if err := c.Svc.Update(ctx, &req); err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: "ok"})
}

// POST /api/v1/stocks/batch_upsert
func (c *StockZhAListController) batchUpsert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req []*model.StockZhAList
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	affected, err := c.Svc.BatchUpsert(ctx, req, 200)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"rows": affected}})
}

// DELETE /api/v1/stocks/all
func (c *StockZhAListController) deleteAll(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	affected, err := c.Svc.DeleteAll(ctx)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"rows": affected}})
}

// GET /api/v1/stocks/count
func (c *StockZhAListController) count(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	f := &model.StockZhAListFilters{
		Exchange: r.URL.Query().Get("exchange"),
		Code:     r.URL.Query().Get("code"),
		Company:  r.URL.Query().Get("company"),
	}
	cnt, err := c.Svc.CountFiltered(ctx, f)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"count": cnt}})
}
