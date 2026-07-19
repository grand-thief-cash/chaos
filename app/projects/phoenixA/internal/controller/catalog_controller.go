package controller

import (
	"context"
	"net/http"
	"strconv"
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

// GET /api/v2/catalog/capabilities
// Returns a lightweight LLM-optimized view of data availability and capabilities.
// Designed for LLM function-call tool registration — smaller payload than data-dictionary.
// When new download tasks are onboarded, their capability is auto-reflected here
// via the tableCapabilityRegistry + per-source DB stats.
func (c *CatalogController) Capabilities(w http.ResponseWriter, r *http.Request) {
	refresh := r.URL.Query().Get("refresh") == "true"
	caps, err := c.Svc.GetCapabilities(r.Context(), refresh)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, caps)
}

// GET /api/v2/catalog/securities/{security_id}/datasets/summary
// Returns per-dataset/data_type row counts and time ranges for a given security.
// Generic discovery API — not BI-specific. Callers use it to learn what data
// exists for a company without running raw queries.
func (c *CatalogController) GetSecurityCoverage(w http.ResponseWriter, r *http.Request) {
	securityIDStr := chi.URLParam(r, "security_id")
	if securityIDStr == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id is required"})
		return
	}
	securityID, err := strconv.ParseUint(securityIDStr, 10, 64)
	if err != nil || securityID == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id"})
		return
	}
	coverage, err := c.Svc.GetSecurityCoverage(r.Context(), securityID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, coverage)
}
