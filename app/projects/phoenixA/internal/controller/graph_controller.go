package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// GraphController handles HTTP endpoints for Neo4j graph operations.
type GraphController struct {
	*core.BaseComponent
	Svc *service.GraphService `infra:"dep:svc_graph"`
}

func NewGraphController() *GraphController {
	return &GraphController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_GRAPH)}
}

func (c *GraphController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *GraphController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// ── Cypher execution ──────────────────────────────────────────────────────

type cypherRequest struct {
	Cypher string         `json:"cypher"`
	Params map[string]any `json:"params"`
}

// POST /api/v1/graph/cypher — read-only Cypher
func (c *GraphController) RunCypher(w http.ResponseWriter, r *http.Request) {
	var req cypherRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if req.Cypher == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "cypher is required"})
		return
	}
	rows, err := c.Svc.RunCypher(r.Context(), req.Cypher, req.Params)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows})
}

// POST /api/v1/graph/cypher/write — write Cypher
func (c *GraphController) RunCypherWrite(w http.ResponseWriter, r *http.Request) {
	var req cypherRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if req.Cypher == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "cypher is required"})
		return
	}
	affected, err := c.Svc.RunCypherWrite(r.Context(), req.Cypher, req.Params)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"affected": affected}})
}

// ── Node/Edge merge ───────────────────────────────────────────────────────

type mergeNodeRequest struct {
	Label      string         `json:"label"`
	MergeKey   string         `json:"merge_key"`
	MergeValue string         `json:"merge_value"`
	Props      map[string]any `json:"props"`
}

// POST /api/v1/graph/nodes/merge
func (c *GraphController) MergeNode(w http.ResponseWriter, r *http.Request) {
	var req mergeNodeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if req.Label == "" || req.MergeKey == "" || req.MergeValue == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "label, merge_key, merge_value required"})
		return
	}
	affected, err := c.Svc.MergeNode(r.Context(), req.Label, req.MergeKey, req.MergeValue, req.Props)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"affected": affected}})
}

// POST /api/v1/graph/nodes/merge-batch
func (c *GraphController) MergeNodeBatch(w http.ResponseWriter, r *http.Request) {
	var reqs []mergeNodeRequest
	if err := json.NewDecoder(r.Body).Decode(&reqs); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	var total int64
	for _, req := range reqs {
		if req.Label == "" || req.MergeKey == "" || req.MergeValue == "" {
			continue
		}
		affected, err := c.Svc.MergeNode(r.Context(), req.Label, req.MergeKey, req.MergeValue, req.Props)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
			return
		}
		total += affected
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"total_affected": total, "count": len(reqs)}})
}

type mergeEdgeRequest struct {
	FromLabel string         `json:"from_label"`
	FromKey   string         `json:"from_key"`
	FromValue string         `json:"from_value"`
	ToLabel   string         `json:"to_label"`
	ToKey     string         `json:"to_key"`
	ToValue   string         `json:"to_value"`
	RelType   string         `json:"rel_type"`
	Attrs     map[string]any `json:"attrs"`
}

// POST /api/v1/graph/edges/merge
func (c *GraphController) MergeEdge(w http.ResponseWriter, r *http.Request) {
	var req mergeEdgeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if req.FromLabel == "" || req.ToLabel == "" || req.RelType == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "from_label, to_label, rel_type required"})
		return
	}
	affected, err := c.Svc.MergeEdge(r.Context(),
		req.FromLabel, req.FromKey, req.FromValue,
		req.ToLabel, req.ToKey, req.ToValue,
		req.RelType, req.Attrs)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"affected": affected}})
}

// POST /api/v1/graph/edges/merge-batch
func (c *GraphController) MergeEdgeBatch(w http.ResponseWriter, r *http.Request) {
	var reqs []mergeEdgeRequest
	if err := json.NewDecoder(r.Body).Decode(&reqs); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	var total int64
	for _, req := range reqs {
		if req.FromLabel == "" || req.ToLabel == "" || req.RelType == "" {
			continue
		}
		affected, err := c.Svc.MergeEdge(r.Context(),
			req.FromLabel, req.FromKey, req.FromValue,
			req.ToLabel, req.ToKey, req.ToValue,
			req.RelType, req.Attrs)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
			return
		}
		total += affected
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"total_affected": total, "count": len(reqs)}})
}

// ── Read queries ──────────────────────────────────────────────────────────

// GET /api/v1/graph/search
func (c *GraphController) SearchNodes(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "q param required"})
		return
	}
	limit := 20
	if l := r.URL.Query().Get("limit"); l != "" {
		if v, err := strconv.Atoi(l); err == nil && v > 0 {
			limit = v
		}
	}
	rows, err := c.Svc.SearchNodes(r.Context(), q, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"query": q, "results": rows, "total": len(rows)}})
}

// GET /api/v1/graph/company/{name}
func (c *GraphController) GetCompanyFull(w http.ResponseWriter, r *http.Request, name string) {
	rows, err := c.Svc.GetCompanyFull(r.Context(), name)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	if len(rows) == 0 {
		writeJSON(w, http.StatusNotFound, apiError{Error: "company not found"})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows[0]})
}

// GET /api/v1/graph/company/{name}/chain
func (c *GraphController) GetCompanyChain(w http.ResponseWriter, r *http.Request, name string) {
	maxHops := 3
	if h := r.URL.Query().Get("max_hops"); h != "" {
		if v, err := strconv.Atoi(h); err == nil && v > 0 {
			maxHops = v
		}
	}
	data, err := c.Svc.GetCompanyChain(r.Context(), name, maxHops)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"company": name, "chain": data}})
}

// GET /api/v1/graph/company/{name}/timeline
func (c *GraphController) GetCompanyTimeline(w http.ResponseWriter, r *http.Request, name string) {
	rows, err := c.Svc.GetCompanyTimeline(r.Context(), name)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"company": name, "timeline": rows}})
}

// GET /api/v1/graph/company/{name}/competitors
func (c *GraphController) GetCompanyCompetitors(w http.ResponseWriter, r *http.Request, name string) {
	rows, err := c.Svc.GetCompetitors(r.Context(), name)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"company": name, "competitors": rows}})
}

// GET /api/v1/graph/event/{name}/impacts
func (c *GraphController) GetEventImpacts(w http.ResponseWriter, r *http.Request, name string) {
	rows, err := c.Svc.GetEventImpacts(r.Context(), name)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"event": name, "impacts": rows}})
}

// GET /api/v1/graph/stats
func (c *GraphController) GetGraphStats(w http.ResponseWriter, r *http.Request) {
	data, err := c.Svc.GetGraphStats(r.Context())
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: data})
}

// POST /api/v1/graph/schema/ensure
func (c *GraphController) EnsureSchema(w http.ResponseWriter, r *http.Request) {
	if err := c.Svc.EnsureSchema(r.Context()); err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]string{"status": "ok"}})
}

