package controller

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"gorm.io/gorm"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// SecurityController handles HTTP endpoints for the unified security registry.
type SecurityController struct {
	*core.BaseComponent
	Svc *service.SecurityService `infra:"dep:svc_security"`
}

func NewSecurityController() *SecurityController {
	return &SecurityController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_SECURITY)}
}

func (c *SecurityController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *SecurityController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// GET /api/v2/securities
func (c *SecurityController) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	limit, offset := parseLimitOffset(r)
	q := r.URL.Query()

	symbols := parseFieldsParam(q.Get("symbols"))
	if symbolList := q.Get("symbol_list"); symbolList != "" {
		symbols = append(symbols, strings.Split(symbolList, ",")...)
	}
	exchanges := parseFieldsParam(q.Get("exchange"))

	singleSymbol := ""
	if len(symbols) == 1 {
		singleSymbol = symbols[0]
	}

	f := &model.SecurityFilters{
		Symbol:    singleSymbol,
		Symbols:   symbols,
		AssetType: q.Get("asset_type"),
		Market:    q.Get("market"),
		Exchanges: exchanges,
		Name:      q.Get("name"),
		Status:    q.Get("status"),
	}
	hasSecurityID := false
	if sid := q.Get("security_id"); sid != "" {
		id, err := strconv.ParseUint(sid, 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id"})
			return
		}
		f.SecurityID = id
		hasSecurityID = true
	}
	// Defaults: only apply when not querying by id — id uniquely identifies the
	// row, and coupling an id query to default asset_type/market would silently
	// filter out non-stock rows once more asset types exist.
	if !hasSecurityID {
		if f.AssetType == "" {
			f.AssetType = bizConsts.ASSET_TYPE_STOCK
		}
		if f.Market == "" {
			f.Market = bizConsts.MARKET_ZH_A
		}
	}

	list, err := c.Svc.ListFiltered(ctx, f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// GET /api/v2/securities/search
//
// One-pass search returning {items, total, limit, offset} computed over a
// single L1 snapshot, so list and count cannot diverge (the legacy
// /securities + /securities/count pair had an inconsistency window and doubled
// the work). q is the unified free-text term: symbol exact (case-insensitive)
// OR name contains (case-sensitive) - any one suffices. Legacy name/symbol
// params are still accepted for backward-compatible callers. status is optional
// (delisted securities remain queryable for historical DuPont).
func (c *SecurityController) Search(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	limit, offset := parseLimitOffset(r)
	q := r.URL.Query()

	f := &model.SecurityFilters{
		AssetType: q.Get("asset_type"),
		Market:    q.Get("market"),
		Exchanges: parseFieldsParam(q.Get("exchange")),
		Name:      q.Get("name"),
		Q:         q.Get("q"),
		Status:    q.Get("status"),
		Symbol:    q.Get("symbol"),
	}
	// Default scope to stock/zh_a so the L1 snapshot key is well-defined.
	if f.AssetType == "" {
		f.AssetType = bizConsts.ASSET_TYPE_STOCK
	}
	if f.Market == "" {
		f.Market = bizConsts.MARKET_ZH_A
	}

	res, err := c.Svc.SearchPage(ctx, f, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: res})
}

// GET /api/v2/securities/{security_id}
func (c *SecurityController) Get(w http.ResponseWriter, r *http.Request, securityIDStr string) {
	ctx := r.Context()
	securityID, err := strconv.ParseUint(securityIDStr, 10, 64)
	if err != nil || securityID == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id"})
		return
	}
	s, err := c.Svc.GetByID(ctx, securityID)
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

// POST /api/v2/securities/upsert
func (c *SecurityController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req []*model.SecurityRegistry
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

// GET /api/v2/securities/count
func (c *SecurityController) Count(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	q := r.URL.Query()
	f := &model.SecurityFilters{
		AssetType: q.Get("asset_type"),
		Market:    q.Get("market"),
		Exchanges: parseFieldsParam(q.Get("exchange")),
		Name:      q.Get("name"),
		Status:    q.Get("status"),
	}
	if f.AssetType == "" {
		f.AssetType = bizConsts.ASSET_TYPE_STOCK
	}
	if f.Market == "" {
		f.Market = bizConsts.MARKET_ZH_A
	}
	cnt, err := c.Svc.CountFiltered(ctx, f)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"count": cnt}})
}

// DELETE /api/v2/securities/all
func (c *SecurityController) DeleteAll(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	q := r.URL.Query()
	assetType := q.Get("asset_type")
	market := q.Get("market")
	affected, err := c.Svc.DeleteAll(ctx, assetType, market)
	if err != nil {
		writeServiceError(w, err) // ConflictError (referenced) → 409; other → 500
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"rows": affected}})
}
