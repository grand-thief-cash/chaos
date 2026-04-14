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

// TaxonomyController handles HTTP endpoints for unified taxonomy data.
type TaxonomyController struct {
	*core.BaseComponent
	Svc *service.TaxonomyService `infra:"dep:svc_taxonomy"`
}

func NewTaxonomyController() *TaxonomyController {
	return &TaxonomyController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_TAXONOMY)}
}

func (c *TaxonomyController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *TaxonomyController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/taxonomy/{source}/categories/upsert
func (c *TaxonomyController) BatchUpsertCategories(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	if source == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "source is required"})
		return
	}
	var list []*model.TaxonomyCategory
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.BatchUpsertCategories(r.Context(), source, list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(list)})
}

// GET /api/v2/taxonomy/{source}/categories
func (c *TaxonomyController) ListCategories(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
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

	list, count, err := c.Svc.ListCategories(r.Context(), source, f, page, pageSize)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"list": list, "total": count})
}

// GET /api/v2/taxonomy/{source}/categories/{code}
func (c *TaxonomyController) GetCategory(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	code := chi.URLParam(r, "code")
	cat, err := c.Svc.GetCategory(r.Context(), source, code)
	if err != nil {
		writeJSON(w, http.StatusNotFound, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, cat)
}

// DELETE /api/v2/taxonomy/{source}/categories/{code}
func (c *TaxonomyController) DeleteCategory(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	code := chi.URLParam(r, "code")
	if err := c.Svc.DeleteCategory(r.Context(), source, code); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// POST /api/v2/taxonomy/{source}/mapping/upsert
func (c *TaxonomyController) BatchUpsertMappings(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	var list []*model.TaxonomySecurityMap
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.BatchUpsertMappings(r.Context(), source, list); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/mapping/replace/by_symbol
func (c *TaxonomyController) ReplaceCategoriesForSymbols(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.ReplaceCategoriesForSymbols(r.Context(), source, payload); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// POST /api/v2/taxonomy/{source}/mapping/replace/by_category
func (c *TaxonomyController) ReplaceStocksForCategories(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.ReplaceStocksForCategories(r.Context(), source, payload); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

// GET /api/v2/taxonomy/{source}/mapping/by_category/{categoryCode}
func (c *TaxonomyController) ListMappingsByCategory(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	categoryCode := chi.URLParam(r, "categoryCode")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, err := c.Svc.ListMappingsByCategory(r.Context(), source, categoryCode, page, pageSize)
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

// DELETE /api/v2/taxonomy/{source}/mapping/{categoryCode}/{symbol}
func (c *TaxonomyController) DeleteMapping(w http.ResponseWriter, r *http.Request) {
	source := chi.URLParam(r, "source")
	categoryCode := chi.URLParam(r, "categoryCode")
	symbol := chi.URLParam(r, "symbol")
	if err := c.Svc.DeleteMapping(r.Context(), source, categoryCode, symbol); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
