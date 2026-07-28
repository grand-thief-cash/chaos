package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

var validGovernanceKinds = map[string]bool{
	"discovery": true, "semantic-version": true, "crosswalk": true,
}

var validAtlasClaimTypes = map[string]bool{
	"RELATION": true, "QUANTIFIED": true, "ANALYST_VIEW": true,
}

var validAtlasAssertionTypes = map[string]bool{
	"OBSERVED_FACT": true, "COMPANY_DISCLOSURE": true,
	"MANAGEMENT_PLAN": true, "ANALYST_ESTIMATE": true,
	"ANALYST_OPINION": true, "FORECAST": true,
	"SCENARIO_ASSUMPTION": true,
}

var validAtlasClaimStatuses = map[string]bool{
	"ACCEPTED": true, "REVIEW_REQUIRED": true, "REJECTED": true,
}

type AtlasKGController struct {
	*core.BaseComponent
	Svc *service.AtlasKGService `infra:"dep:svc_atlas_kg"`
}

func NewAtlasKGController() *AtlasKGController {
	return &AtlasKGController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_ATLAS_KG)}
}
func (c *AtlasKGController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *AtlasKGController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

func decodeAtlasRun(r *http.Request) (*model.AtlasExtractionRun, error) {
	var payload json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		return nil, err
	}
	var fields struct {
		ID               string `json:"id"`
		SourceDocumentID string `json:"source_document_id"`
		SourceReportType string `json:"source_report_type"`
		Status           string `json:"status"`
	}
	if err := json.Unmarshal(payload, &fields); err != nil {
		return nil, err
	}
	return &model.AtlasExtractionRun{
		ID: fields.ID, SourceDocumentID: fields.SourceDocumentID,
		SourceReportType: fields.SourceReportType, Status: fields.Status, Payload: payload,
	}, nil
}

func (c *AtlasKGController) CreateExtractionRun(w http.ResponseWriter, r *http.Request) {
	run, err := decodeAtlasRun(r)
	if err != nil || uuid.Validate(run.ID) != nil || run.SourceDocumentID == "" || run.Status == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid id, source_document_id and status are required"})
		return
	}
	if err := c.Svc.UpsertExtractionRun(r.Context(), run); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, run)
}

func (c *AtlasKGController) UpdateExtractionRun(w http.ResponseWriter, r *http.Request) {
	run, err := decodeAtlasRun(r)
	runID := chi.URLParam(r, "run_id")
	if err != nil || uuid.Validate(runID) != nil || (run.ID != "" && run.ID != runID) {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid or mismatched run id"})
		return
	}
	run.ID = runID
	if err := c.Svc.UpsertExtractionRun(r.Context(), run); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (c *AtlasKGController) SaveExtractionResult(w http.ResponseWriter, r *http.Request) {
	runID := chi.URLParam(r, "run_id")
	var payload json.RawMessage
	if uuid.Validate(runID) != nil || json.NewDecoder(r.Body).Decode(&payload) != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "valid run id and JSON object are required"})
		return
	}
	if err := c.Svc.SaveExtractionResult(r.Context(), runID, payload); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (c *AtlasKGController) GetExtractionRun(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.GetExtractionRun(r.Context(), chi.URLParam(r, "run_id"))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (c *AtlasKGController) ListExtractionRuns(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.ListExtractionRuns(r.Context(), r.URL.Query().Get("status"), queryLimit(r))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func (c *AtlasKGController) FindCompletedExtractionRun(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query()
	sourceDocumentID := query.Get("source_document_id")
	semanticVersion := query.Get("semantic_version")
	pipelineVersion := query.Get("pipeline_version")
	if sourceDocumentID == "" || semanticVersion == "" || pipelineVersion == "" {
		writeJSON(w, http.StatusBadRequest, apiError{
			Error: "source_document_id, semantic_version and pipeline_version are required",
		})
		return
	}
	result, err := c.Svc.FindCompletedExtractionRun(
		r.Context(), sourceDocumentID, semanticVersion, pipelineVersion,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (c *AtlasKGController) FindReusableExtraction(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query()
	sourceDocumentID := query.Get("source_document_id")
	semanticVersion := query.Get("semantic_version")
	pipelineVersion := query.Get("pipeline_version")
	promptSignature := query.Get("prompt_signature")
	if sourceDocumentID == "" ||
		semanticVersion == "" ||
		pipelineVersion == "" ||
		promptSignature == "" {
		writeJSON(w, http.StatusBadRequest, apiError{
			Error: "source_document_id, semantic_version, pipeline_version and prompt_signature are required",
		})
		return
	}
	result, err := c.Svc.FindReusableExtraction(
		r.Context(),
		sourceDocumentID,
		semanticVersion,
		pipelineVersion,
		promptSignature,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (c *AtlasKGController) SaveGovernanceRecord(w http.ResponseWriter, r *http.Request) {
	kind := chi.URLParam(r, "kind")
	if !validGovernanceKinds[kind] {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid governance kind"})
		return
	}
	var payload json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	var fields struct {
		ID      string `json:"run_id"`
		Version string `json:"version"`
		Status  string `json:"status"`
	}
	_ = json.Unmarshal(payload, &fields)
	if fields.ID == "" {
		fields.ID = uuid.NewString()
	}
	record := &model.AtlasGovernanceRecord{
		ID: fields.ID, Kind: kind, Version: fields.Version, Status: fields.Status, Payload: payload,
	}
	if record.Status == "" {
		record.Status = "PROPOSED"
	}
	if err := c.Svc.SaveGovernance(r.Context(), record); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, record)
}

func (c *AtlasKGController) ListGovernanceRecords(w http.ResponseWriter, r *http.Request) {
	kind := chi.URLParam(r, "kind")
	if !validGovernanceKinds[kind] {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid governance kind"})
		return
	}
	result, err := c.Svc.ListGovernance(r.Context(), kind, queryLimit(r))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func (c *AtlasKGController) UpsertEntities(w http.ResponseWriter, r *http.Request) {
	var items []*model.AtlasKnowledgeEntity
	if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := validateAtlasEntities(items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.UpsertEntities(r.Context(), items); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(items)})
}

func validateAtlasEntities(items []*model.AtlasKnowledgeEntity) error {
	if len(items) > 2000 {
		return fmt.Errorf("at most 2000 entities are allowed per request")
	}
	for index, item := range items {
		if item == nil ||
			uuid.Validate(item.ID) != nil ||
			item.CanonicalName == "" ||
			item.NormalizedName == "" ||
			item.EntityType == "" ||
			item.ResolutionState == "" ||
			len(item.Attributes) == 0 {
			return fmt.Errorf("invalid Atlas entity at index %d", index)
		}
	}
	return nil
}

func (c *AtlasKGController) ListEntities(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.ListEntities(
		r.Context(),
		r.URL.Query().Get("q"),
		r.URL.Query().Get("entity_type"),
		r.URL.Query().Get("match") == "exact",
		queryLimit(r),
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func (c *AtlasKGController) UpsertEntityAliases(w http.ResponseWriter, r *http.Request) {
	var items []*model.AtlasEntityAlias
	if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := validateEntityAliases(items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.UpsertEntityAliases(r.Context(), items); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(items)})
}

func validateEntityAliases(items []*model.AtlasEntityAlias) error {
	if len(items) > 2000 {
		return fmt.Errorf("at most 2000 aliases are allowed per request")
	}
	for index, item := range items {
		if item == nil ||
			uuid.Validate(item.EntityID) != nil ||
			item.Alias == "" ||
			item.NormalizedAlias == "" {
			return fmt.Errorf("invalid entity alias at index %d", index)
		}
	}
	return nil
}

func (c *AtlasKGController) UpsertSecurityEntityLinks(w http.ResponseWriter, r *http.Request) {
	var items []*model.AtlasSecurityEntityLink
	if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := validateSecurityEntityLinks(items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.UpsertSecurityEntityLinks(r.Context(), items); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(items)})
}

func (c *AtlasKGController) UpsertClaims(w http.ResponseWriter, r *http.Request) {
	var items []*model.AtlasClaim
	if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := validateAtlasClaims(items); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	if err := c.Svc.UpsertClaims(r.Context(), items); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(items)})
}

func validateAtlasClaims(items []*model.AtlasClaim) error {
	if len(items) > 5000 {
		return fmt.Errorf("at most 5000 claims are allowed per request")
	}
	for index, item := range items {
		if item == nil ||
			uuid.Validate(item.ID) != nil ||
			item.SourceDocumentID == "" ||
			!validAtlasClaimTypes[item.ClaimType] ||
			!validAtlasAssertionTypes[item.AssertionType] ||
			!validAtlasClaimStatuses[item.Status] ||
			!isJSONObject(item.Payload) {
			return fmt.Errorf("invalid Atlas claim at index %d", index)
		}
		switch item.ClaimType {
		case "RELATION":
			if item.SubjectEntityID == nil ||
				uuid.Validate(*item.SubjectEntityID) != nil ||
				item.ObjectEntityID == nil ||
				uuid.Validate(*item.ObjectEntityID) != nil ||
				item.CanonicalPredicate == "" {
				return fmt.Errorf("invalid relation claim at index %d", index)
			}
		case "QUANTIFIED":
			if item.SubjectEntityID == nil ||
				uuid.Validate(*item.SubjectEntityID) != nil {
				return fmt.Errorf("invalid quantified claim at index %d", index)
			}
		case "ANALYST_VIEW":
			if item.SubjectEntityID != nil &&
				uuid.Validate(*item.SubjectEntityID) != nil {
				return fmt.Errorf("invalid analyst view at index %d", index)
			}
		}
	}
	return nil
}

func isJSONObject(payload json.RawMessage) bool {
	var object map[string]any
	return len(payload) > 0 &&
		json.Unmarshal(payload, &object) == nil &&
		object != nil
}

func validateSecurityEntityLinks(items []*model.AtlasSecurityEntityLink) error {
	if len(items) > 2000 {
		return fmt.Errorf("at most 2000 links are allowed per request")
	}
	for index, item := range items {
		if item == nil ||
			uuid.Validate(item.EntityID) != nil ||
			item.SecurityID <= 0 ||
			item.Confidence < 0 ||
			item.Confidence > 1 ||
			item.ResolutionMethod == "" {
			return fmt.Errorf("invalid security entity link at index %d", index)
		}
	}
	return nil
}

func (c *AtlasKGController) ListClaims(w http.ResponseWriter, r *http.Request) {
	result, err := c.Svc.ListClaims(r.Context(), r.URL.Query().Get("entity_id"), r.URL.Query().Get("predicate"), queryLimit(r))
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": result})
}

func queryLimit(r *http.Request) int {
	value, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	return value
}
