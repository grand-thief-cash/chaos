package controller

import (
	"context"
	"encoding/json"
	"errors"
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
//
// Phase 2 surrogate-key refactor: mapping/constituent/weight/daily endpoints are keyed by
// security_id / category_id (path params + payloads). The industry upsert endpoints still
// ACCEPT SDK natural keys (index_code, con_code) in the body — phoenixA resolves them to
// surrogate ids at entry via the service resolve cache before the write buffer / DAO sees
// them (refactor §2.3 / §10.c). Categories keep their natural-key identity (base table).
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

// parseUint64Param extracts a uint64 path param; ok=false if missing/invalid/zero.
func parseUint64Param(r *http.Request, name string) (uint64, bool) {
	raw := chi.URLParam(r, name)
	if raw == "" {
		return 0, false
	}
	v, err := strconv.ParseUint(raw, 10, 64)
	if err != nil || v == 0 {
		return 0, false
	}
	return v, true
}

// writeServiceError maps a service error to the right HTTP status: a service.ValidationError
// (client payload problem — unknown id, unresolvable natural key, empty sync scope) → 400;
// a service.ConflictError (delete blocked by downstream references) → 409; anything else → 500.
func writeServiceError(w http.ResponseWriter, err error) {
	if err == nil {
		return
	}
	var ve *service.ValidationError
	if errors.As(err, &ve) {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	var ce *service.ConflictError
	if errors.As(err, &ce) {
		writeJSON(w, http.StatusConflict, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
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
		writeServiceError(w, err)
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
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "rows_synced": n})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/upsert
// Body: [{security_id, category_id}] (id-keyed; refactor §10.b).
func (c *TaxonomyController) BatchUpsertMappings(w http.ResponseWriter, r *http.Request) {
	var list []*model.TaxonomySecurityMap
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	for _, m := range list {
		if m == nil || m.SecurityID == 0 || m.CategoryID == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "each mapping requires non-zero security_id and category_id"})
			return
		}
	}
	if err := c.Svc.BatchUpsertMappings(r.Context(), list); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_security
// Body: {security_id: [category_id, ...]} (JSON keys are strings; parsed to uint64).
func (c *TaxonomyController) ReplaceCategoriesForSecurities(w http.ResponseWriter, r *http.Request) {
	payload, ok := decodeUint64SliceMap(w, r)
	if !ok {
		return
	}
	if err := c.Svc.ReplaceCategoriesForSecurities(r.Context(), payload); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_category
// Body: {category_id: [security_id, ...]} (JSON keys are strings; parsed to uint64).
func (c *TaxonomyController) ReplaceSecuritiesForCategories(w http.ResponseWriter, r *http.Request) {
	payload, ok := decodeUint64SliceMap(w, r)
	if !ok {
		return
	}
	if err := c.Svc.ReplaceSecuritiesForCategories(r.Context(), payload); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/mapping/by_category/{category_id}
func (c *TaxonomyController) ListMappingsByCategory(w http.ResponseWriter, r *http.Request) {
	categoryID, ok := parseUint64Param(r, "category_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid category_id path param is required"})
		return
	}
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, err := c.Svc.ListMappingsByCategory(r.Context(), categoryID, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// GET /api/v2/taxonomy/by_security/{security_id}
func (c *TaxonomyController) ListMappingsBySecurity(w http.ResponseWriter, r *http.Request) {
	securityID, ok := parseUint64Param(r, "security_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid security_id path param is required"})
		return
	}
	list, err := c.Svc.ListMappingsBySecurity(r.Context(), securityID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// DELETE /api/v2/taxonomy/{source}/{taxonomy}/mapping/{category_id}/{security_id}
func (c *TaxonomyController) DeleteMapping(w http.ResponseWriter, r *http.Request) {
	categoryID, ok := parseUint64Param(r, "category_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid category_id path param is required"})
		return
	}
	securityID, ok := parseUint64Param(r, "security_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid security_id path param is required"})
		return
	}
	if err := c.Svc.DeleteMapping(r.Context(), categoryID, securityID); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// ──────────── Industry Constituents ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/upsert
// Body carries SDK natural keys (index_code, con_code); phoenixA resolves to ids at entry.
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
	if err := c.Svc.ResolveConstituents(r.Context(), source, taxonomy, market, list); err != nil {
		writeServiceError(w, err)
		return
	}
	if err := c.Svc.BatchUpsertConstituents(r.Context(), source, taxonomy, market, list); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_category/{category_id}
func (c *TaxonomyController) ListConstituentsByCategory(w http.ResponseWriter, r *http.Request) {
	categoryID, ok := parseUint64Param(r, "category_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid category_id path param is required"})
		return
	}
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, err := c.Svc.ListConstituentsByCategory(r.Context(), categoryID, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_security/{security_id}
func (c *TaxonomyController) ListConstituentsBySecurity(w http.ResponseWriter, r *http.Request) {
	securityID, ok := parseUint64Param(r, "security_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid security_id path param is required"})
		return
	}
	list, err := c.Svc.ListConstituentsBySecurity(r.Context(), securityID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// ──────────── Industry Weights ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/upsert
// Body carries SDK natural keys; phoenixA resolves to ids at entry (before the write buffer).
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
	if err := c.Svc.ResolveWeights(r.Context(), source, taxonomy, market, list); err != nil {
		writeServiceError(w, err)
		return
	}
	// Route through write buffer for small batches, direct write for large ones.
	if c.BufMgr != nil && c.BufMgr.IsEnabled() && len(list) < c.BufMgr.DirectFlushThreshold() {
		if err := c.BufMgr.SubmitIndustryWeights(source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full"})
			return
		}
	} else {
		if err := c.Svc.BatchUpsertWeights(r.Context(), source, taxonomy, market, list); err != nil {
			writeServiceError(w, err)
			return
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/{category_id}
func (c *TaxonomyController) ListWeightsByCategoryAndDate(w http.ResponseWriter, r *http.Request) {
	categoryID, ok := parseUint64Param(r, "category_id")
	if !ok {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid category_id path param is required"})
		return
	}
	tradeDate := r.URL.Query().Get("trade_date")
	if tradeDate == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "trade_date query param is required"})
		return
	}
	list, err := c.Svc.ListWeightsByCategoryAndDate(r.Context(), categoryID, tradeDate)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "count": len(list)})
}

// ──────────── Industry Daily ────────────

// POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily/upsert
// Body carries SDK natural keys; phoenixA resolves to ids at entry (before the write buffer).
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
	if err := c.Svc.ResolveIndustryDaily(r.Context(), source, taxonomy, market, list); err != nil {
		writeServiceError(w, err)
		return
	}
	if c.BufMgr != nil && c.BufMgr.IsEnabled() && len(list) < c.BufMgr.DirectFlushThreshold() {
		if err := c.BufMgr.SubmitIndustryDaily(source, taxonomy, market, list); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full"})
			return
		}
	} else {
		if err := c.Svc.BatchUpsertIndustryDaily(r.Context(), source, taxonomy, market, list); err != nil {
			writeServiceError(w, err)
			return
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily?category_id=&start_date=&end_date=
func (c *TaxonomyController) QueryIndustryDaily(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	categoryIDStr := q.Get("category_id")
	if categoryIDStr == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "category_id query param is required"})
		return
	}
	categoryID, err := strconv.ParseUint(categoryIDStr, 10, 64)
	if err != nil || categoryID == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid category_id query param is required"})
		return
	}
	startDate := q.Get("start_date")
	endDate := q.Get("end_date")
	limit, _ := strconv.Atoi(q.Get("limit"))

	list, err := c.Svc.QueryIndustryDaily(r.Context(), categoryID, startDate, endDate, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": list, "count": len(list)})
}

// decodeUint64SliceMap decodes a JSON object {string-key: [uint64,...]} into
// map[uint64][]uint64. JSON object keys are always strings, so they must be parsed.
// Rejects zero ids (keys or values) so orphan-id writes can't slip through (the service
// additionally validates existence against the resolve cache).
func decodeUint64SliceMap(w http.ResponseWriter, r *http.Request) (map[uint64][]uint64, bool) {
	var raw map[string][]uint64
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return nil, false
	}
	out := make(map[uint64][]uint64, len(raw))
	for k, vs := range raw {
		id, err := strconv.ParseUint(k, 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "mapping keys must be non-zero uint64 ids"})
			return nil, false
		}
		for _, v := range vs {
			if v == 0 {
				writeJSON(w, http.StatusBadRequest, apiError{Error: "mapping values must be non-zero uint64 ids"})
				return nil, false
			}
		}
		out[id] = vs
	}
	return out, true
}
