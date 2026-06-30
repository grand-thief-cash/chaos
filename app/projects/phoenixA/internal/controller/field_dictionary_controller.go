package controller

import (
	"context"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// FieldDictionaryController exposes the AmazingData field dictionary via the
// Phase 2 discovery APIs:
//
//	GET /api/v2/catalog/datasets
//	GET /api/v2/catalog/datasets/{dataset}/fields
//	GET /api/v2/catalog/enums/{enum_name}
type FieldDictionaryController struct {
	*core.BaseComponent
	Svc *service.FieldDictionaryService `infra:"dep:svc_field_dictionary"`
}

func NewFieldDictionaryController() *FieldDictionaryController {
	return &FieldDictionaryController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_FIELD_DICTIONARY),
	}
}

func (c *FieldDictionaryController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}
func (c *FieldDictionaryController) Stop(ctx context.Context) error { return c.BaseComponent.Stop(ctx) }

// GET /api/v2/catalog/datasets?source=amazing_data
func (c *FieldDictionaryController) ListDatasets(w http.ResponseWriter, r *http.Request) {
	source := r.URL.Query().Get("source")
	resp, err := c.Svc.ListDatasets(r.Context(), source)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

// GET /api/v2/catalog/datasets/{dataset}/fields
//
// Query params:
//
//	source          - data source (default amazing_data)
//	type            - data_type filter (balance_sheet, income, cashflow, ...)
//	include         - "core" (default) | "all" | "metadata"
//	search          - substring match on raw_field/canonical_field/label_zh/description
//	comp_type_scope - all | non_financial | bank | insurance | securities
//	include_deprecated - "true" to include deprecated fields
func (c *FieldDictionaryController) DiscoverFields(w http.ResponseWriter, r *http.Request) {
	dataset := chi.URLParam(r, "dataset")
	if dataset == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "dataset is required"})
		return
	}

	q := r.URL.Query()
	params := dao.FieldQueryParams{
		Source:            q.Get("source"),
		DataType:          q.Get("type"),
		Include:           q.Get("include"),
		Search:            q.Get("search"),
		CompTypeScope:     q.Get("comp_type_scope"),
		IncludeDeprecated: q.Get("include_deprecated") == "true",
	}

	resp, err := c.Svc.DiscoverFields(r.Context(), dataset, params)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	if len(resp.Fields) == 0 {
		// Distinguish "dataset exists but no fields matched" from "dataset
		// unknown". The latter is a 404 to help callers debug typos.
		writeJSON(w, http.StatusNotFound, apiError{
			Error: "no fields found for dataset " + dataset + " with the given filters",
		})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

// GET /api/v2/catalog/enums/{enum_name}?source=amazing_data
func (c *FieldDictionaryController) GetEnum(w http.ResponseWriter, r *http.Request) {
	enumName := chi.URLParam(r, "enum_name")
	if enumName == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "enum_name is required"})
		return
	}
	source := r.URL.Query().Get("source")

	resp, err := c.Svc.GetEnum(r.Context(), enumName, source)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	if len(resp.Values) == 0 {
		writeJSON(w, http.StatusNotFound, apiError{
			Error: "enum " + enumName + " not found for source " + resp.Source,
		})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}
