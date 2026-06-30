package controller

import (
	"context"
	"net/http"
	"strconv"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// FieldCoverageController exposes the field coverage observation API:
//
//	POST /api/v2/catalog/field-coverage/scan?dataset=X&source=Y&sample_limit=N
//	GET  /api/v2/catalog/field-coverage?dataset=X&source=Y&status=ungoverned
type FieldCoverageController struct {
	*core.BaseComponent
	Svc *service.FieldCoverageService `infra:"dep:svc_field_coverage"`
}

func NewFieldCoverageController() *FieldCoverageController {
	return &FieldCoverageController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_FIELD_COVERAGE),
	}
}

func (c *FieldCoverageController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *FieldCoverageController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/catalog/field-coverage/scan?dataset=&source=&sample_limit=
//
// Triggers a scan. Without dataset=, scans all governed datasets. Returns
// per-dataset summaries including ungoverned keys found.
func (c *FieldCoverageController) Scan(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	dataset := q.Get("dataset")
	source := q.Get("source")
	sampleLimit, _ := strconv.Atoi(q.Get("sample_limit"))

	results, err := c.Svc.ScanDataset(r.Context(), dataset, source, sampleLimit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status":  "ok",
		"scanned": len(results),
		"results": results,
	})
}

// GET /api/v2/catalog/field-coverage?dataset=&source=&status=
//
// Lists observations. status=ungoverned returns only ungoverned keys.
func (c *FieldCoverageController) List(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	resp, err := c.Svc.ListObservations(r.Context(), q.Get("dataset"), q.Get("source"), q.Get("status"))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}
