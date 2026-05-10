package controller

import (
	"context"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// CatalogController handles data catalog endpoints.
type CatalogController struct {
	*core.BaseComponent
	Svc *service.CatalogService `infra:"dep:svc_catalog"`
}

func NewCatalogController() *CatalogController {
	return &CatalogController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_CATALOG)}
}

func (c *CatalogController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *CatalogController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// GET /api/v2/catalog/overview
func (c *CatalogController) Overview(w http.ResponseWriter, r *http.Request) {
	refresh := r.URL.Query().Get("refresh") == "true"
	overview, err := c.Svc.GetOverview(r.Context(), refresh)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, overview)
}

// GET /api/v2/catalog/tables
func (c *CatalogController) ListTables(w http.ResponseWriter, r *http.Request) {
	domain := r.URL.Query().Get("domain")
	refresh := r.URL.Query().Get("refresh") == "true"
	tables, err := c.Svc.ListTables(r.Context(), domain, refresh)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"tables": tables})
}

// GET /api/v2/catalog/tables/{schema}/{table}
func (c *CatalogController) GetTableDetail(w http.ResponseWriter, r *http.Request) {
	schema := chi.URLParam(r, "schema")
	table := chi.URLParam(r, "table")
	refresh := r.URL.Query().Get("refresh") == "true"

	if schema == "" || table == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "schema and table are required"})
		return
	}

	detail, err := c.Svc.GetTableDetail(r.Context(), schema, table, refresh)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeJSON(w, http.StatusNotFound, apiError{Error: err.Error()})
		} else {
			writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		}
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

// GET /api/v2/catalog/storage
func (c *CatalogController) StorageInfo(w http.ResponseWriter, r *http.Request) {
	info, err := c.Svc.GetStorageInfo(r.Context())
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, info)
}

// GET /api/v2/catalog/graph
func (c *CatalogController) GraphCatalog(w http.ResponseWriter, r *http.Request) {
	info, err := c.Svc.GetGraphCatalog(r.Context())
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, info)
}

// GET /api/v2/catalog/data-dictionary
// Returns comprehensive metadata for all tables — suitable for UI and LLM function calling.
func (c *CatalogController) DataDictionary(w http.ResponseWriter, r *http.Request) {
	refresh := r.URL.Query().Get("refresh") == "true"
	dict, err := c.Svc.GetDataDictionary(r.Context(), refresh)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, dict)
}

// GET /api/v2/catalog/business-overview
func (c *CatalogController) BusinessOverview(w http.ResponseWriter, r *http.Request) {
	refresh := r.URL.Query().Get("refresh") == "true"
	overview, err := c.Svc.GetBusinessOverview(r.Context(), refresh)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, overview)
}
