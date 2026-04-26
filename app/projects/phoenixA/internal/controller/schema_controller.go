package controller

import (
	"context"
	"net/http"
	"strconv"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

// SchemaController handles schema discovery endpoints.
type SchemaController struct {
	*core.BaseComponent
	SchemaDao *dao.SchemaDao `infra:"dep:dao_schema"`
}

func NewSchemaController() *SchemaController {
	return &SchemaController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_SCHEMA)}
}

func (c *SchemaController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *SchemaController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// GET /api/v2/schema/fields?domain=financial_statement&type=balance_sheet&sample_size=500
func (c *SchemaController) DiscoverFields(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	domain := q.Get("domain")
	dataType := q.Get("type")
	sampleSize, _ := strconv.Atoi(q.Get("sample_size"))

	if domain == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "domain is required (financial_statement | corporate_action)"})
		return
	}
	if dataType == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "type is required (e.g. balance_sheet, dividend)"})
		return
	}

	result, err := c.SchemaDao.DiscoverFields(r.Context(), domain, dataType, sampleSize)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, result)
}

// GET /api/v2/schema/overview
func (c *SchemaController) Overview(w http.ResponseWriter, r *http.Request) {
	summaries, err := c.SchemaDao.Overview(r.Context())
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"domains": summaries})
}

// GET /api/v2/schema/domains
func (c *SchemaController) ListDomains(w http.ResponseWriter, r *http.Request) {
	domains := c.SchemaDao.ListDomains()
	writeJSON(w, http.StatusOK, map[string]any{"domains": domains})
}

// GET /api/v2/schema/types?domain=financial_statement
func (c *SchemaController) ListTypes(w http.ResponseWriter, r *http.Request) {
	domain := r.URL.Query().Get("domain")
	if domain == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "domain is required"})
		return
	}
	types, err := c.SchemaDao.ListTypes(r.Context(), domain)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"domain": domain, "types": types})
}
