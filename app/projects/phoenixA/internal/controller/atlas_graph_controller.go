package controller

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type AtlasGraphController struct {
	*core.BaseComponent
	Svc *service.AtlasGraphService `infra:"dep:svc_atlas_graph"`
}

func NewAtlasGraphController() *AtlasGraphController {
	return &AtlasGraphController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_ATLAS_GRAPH)}
}
func (c *AtlasGraphController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *AtlasGraphController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

func (c *AtlasGraphController) ProjectBatch(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Entities []map[string]any `json:"entities"`
		Claims   []map[string]any `json:"claims"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := validateProjection(body.Entities, body.Claims); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.ProjectBatch(r.Context(), body.Entities, body.Claims); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"entities": len(body.Entities), "claims": len(body.Claims)})
}

func (c *AtlasGraphController) SearchNodes(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.Search(r.Context(), r.URL.Query().Get("q"), queryLimit(r))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func (c *AtlasGraphController) GetNeighborhood(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.Neighborhood(r.Context(), chi.URLParam(r, "entity_id"), queryLimit(r))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func (c *AtlasGraphController) GetGraphStats(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.Stats(r.Context())
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}
