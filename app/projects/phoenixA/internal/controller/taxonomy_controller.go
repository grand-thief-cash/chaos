package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/buffer"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// TaxonomyController handles HTTP endpoints for unified taxonomy data.
type TaxonomyController struct {
	*core.BaseComponent
	Svc    *service.TaxonomyService   `infra:"dep:svc_taxonomy"`
	BufMgr *buffer.WriteBufferManager `infra:"dep:write_buffer_mgr"`
}

// BufferManager is the interface the controller needs from the write buffer.
type BufferManager interface {
	IsEnabled() bool
	DirectFlushThreshold() int
	SubmitIndustryWeights(source, taxonomy, market string, weights []*model.IndustryWeight) error
	SubmitIndustryDaily(source, taxonomy, market string, daily []*model.IndustryDaily) error
}

func NewTaxonomyController() *TaxonomyController {
	return &TaxonomyController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_TAXONOMY)}
}

func (c *TaxonomyController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *TaxonomyController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// helper to extract source/taxonomy/market from URL
func taxonomyParams(r *http.Request) (source, taxonomy, market string) {
	source = chi.URLParam(r, "source")
	taxonomy = chi.URLParam(r, "taxonomy")
	market = chi.URLParam(r, "market")
	return
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/upsert
func (c *TaxonomyController) BatchUpsertCategories(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	if source == "" || taxonomy == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and taxonomy are required"})
		return
	}
	var list []*model.TaxonomyCategory
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.BatchUpsertCategories(r.Context(), source, taxonomy, market, list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories
func (c *TaxonomyController) ListCategories(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	pageSize, _ := strconv.Atoi(q.Get("page_size"))

	f := &model.TaxonomyCategoryFilters{}
	if v := q.Get("parent_code"); v != "" {
		f.ParentCode = &v
	}
	if v := q.Get("level"); v != "" {
		if i, err := strconv.ParseUint(v, 10, 8); err == nil {
			u8 := uint8(i)
			f.Level = &u8
		}
	}
	if v := q.Get("name"); v != "" {
		f.Name = v
	}

	list, count, err := c.Svc.ListCategories(r.Context(), source, taxonomy, market, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "total": count})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/{code}
func (c *TaxonomyController) GetCategory(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	code := chi.URLParam(r, "code")
	cat, err := c.Svc.GetCategory(r.Context(), source, taxonomy, market, code)
	if err != nil {
		writeJSON(w, http.StatusNotFound, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, cat)
}

// DELETE /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/{code}
func (c *TaxonomyController) DeleteCategory(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	code := chi.URLParam(r, "code")
	if err := c.Svc.DeleteCategory(r.Context(), source, taxonomy, market, code); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/mapping/sync_from_constituents
func (c *TaxonomyController) SyncMappingsFromConstituents(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	if source == "" || taxonomy == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and taxonomy are required"})
		return
	}
	n, err := c.Svc.SyncMappingsFromConstituents(r.Context(), source, taxonomy, market)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "rows_synced": n})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/upsert
func (c *TaxonomyController) BatchUpsertMappings(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	var list []*model.TaxonomySecurityMap
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.BatchUpsertMappings(r.Context(), source, taxonomy, list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_symbol
func (c *TaxonomyController) ReplaceCategoriesForSymbols(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.ReplaceCategoriesForSymbols(r.Context(), source, taxonomy, payload); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_category
func (c *TaxonomyController) ReplaceStocksForCategories(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.ReplaceStocksForCategories(r.Context(), source, taxonomy, payload); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/mapping/by_category/{categoryCode}
func (c *TaxonomyController) ListMappingsByCategory(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	categoryCode := chi.URLParam(r, "categoryCode")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, err := c.Svc.ListMappingsByCategory(r.Context(), source, taxonomy, categoryCode, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// GET /api/v2/taxonomy/by_security/{symbol}
func (c *TaxonomyController) ListMappingsBySymbol(w http.ResponseWriter, r *http.Request) {
	symbol := chi.URLParam(r, "symbol")
	list, err := c.Svc.ListMappingsBySymbol(r.Context(), symbol)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// DELETE /api/v2/taxonomy/{source}/{taxonomy}/mapping/{categoryCode}/{symbol}
func (c *TaxonomyController) DeleteMapping(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	categoryCode := chi.URLParam(r, "categoryCode")
	symbol := chi.URLParam(r, "symbol")
	if err := c.Svc.DeleteMapping(r.Context(), source, taxonomy, categoryCode, symbol); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// ──────────── Industry Constituents ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/upsert
func (c *TaxonomyController) BatchUpsertConstituents(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	if source == "" || taxonomy == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and taxonomy are required"})
		return
	}
	var list []*model.IndustryConstituent
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.BatchUpsertConstituents(r.Context(), source, taxonomy, market, list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_index/{indexCode}
func (c *TaxonomyController) ListConstituentsByIndex(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	indexCode := chi.URLParam(r, "indexCode")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, err := c.Svc.ListConstituentsByIndex(r.Context(), source, taxonomy, indexCode, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_stock/{symbol}
func (c *TaxonomyController) ListConstituentsBySymbol(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	symbol := chi.URLParam(r, "symbol")
	list, err := c.Svc.ListConstituentsBySymbol(r.Context(), source, taxonomy, symbol)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// ──────────── Industry Weights ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/upsert
func (c *TaxonomyController) BatchUpsertWeights(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	if source == "" || taxonomy == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and taxonomy are required"})
		return
	}
	var list []*model.IndustryWeight
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, w := range list {
		w.TradeDate = normalizeDateYYYYMMDD(w.TradeDate)
	}
	// Route through write buffer for small batches, direct write for large ones
	if c.BufMgr != nil && c.BufMgr.IsEnabled() && len(list) < c.BufMgr.DirectFlushThreshold() {
		if err := c.BufMgr.SubmitIndustryWeights(source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full"})
			return
		}
	} else {
		if err := c.Svc.BatchUpsertWeights(r.Context(), source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
			return
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/{indexCode}
func (c *TaxonomyController) ListWeightsByIndexAndDate(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	indexCode := chi.URLParam(r, "indexCode")
	tradeDate := r.URL.Query().Get("trade_date")
	if tradeDate == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "trade_date query param is required"})
		return
	}
	list, err := c.Svc.ListWeightsByIndexAndDate(r.Context(), source, taxonomy, indexCode, tradeDate)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "count": len(list)})
}

// ──────────── Industry Daily ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily/upsert
func (c *TaxonomyController) BatchUpsertIndustryDaily(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, market := taxonomyParams(r)
	if source == "" || taxonomy == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source and taxonomy are required"})
		return
	}
	var list []*model.IndustryDaily
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, r := range list {
		r.TradeDate = normalizeDateYYYYMMDD(r.TradeDate)
	}
	if c.BufMgr != nil && c.BufMgr.IsEnabled() && len(list) < c.BufMgr.DirectFlushThreshold() {
		if err := c.BufMgr.SubmitIndustryDaily(source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full"})
			return
		}
	} else {
		if err := c.Svc.BatchUpsertIndustryDaily(r.Context(), source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
			return
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily
func (c *TaxonomyController) QueryIndustryDaily(w http.ResponseWriter, r *http.Request) {
	source, taxonomy, _ := taxonomyParams(r)
	q := r.URL.Query()
	indexCode := q.Get("index_code")
	if indexCode == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "index_code query param is required"})
		return
	}
	startDate := q.Get("start_date")
	endDate := q.Get("end_date")
	limit, _ := strconv.Atoi(q.Get("limit"))

	list, err := c.Svc.QueryIndustryDaily(r.Context(), source, taxonomy, indexCode, startDate, endDate, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "count": len(list)})
}
