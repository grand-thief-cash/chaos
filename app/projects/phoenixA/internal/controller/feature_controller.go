package controller

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type FeatureController struct {
	*core.BaseComponent
	Registry *service.FeatureRegistryService `infra:"dep:svc_feature_registry"`
	Runs     *service.FeatureRunService      `infra:"dep:svc_feature_run"`
}

func NewFeatureController() *FeatureController {
	return &FeatureController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_FEATURE)}
}

func (c *FeatureController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *FeatureController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

func decodeFeatureJSON(w http.ResponseWriter, r *http.Request, target any) bool {
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		writeJSON(w, http.StatusBadRequest, model.FeaturePlatformError{Code: "INVALID_JSON", Message: err.Error()})
		return false
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		writeJSON(w, http.StatusBadRequest, model.FeaturePlatformError{Code: "INVALID_JSON", Message: "request body must contain exactly one JSON value"})
		return false
	}
	return true
}

func writeFeatureError(w http.ResponseWriter, err error) {
	var featureErr *model.FeaturePlatformError
	if errors.As(err, &featureErr) {
		status := http.StatusInternalServerError
		switch featureErr.Kind {
		case model.FeatureErrorValidation:
			status = http.StatusBadRequest
		case model.FeatureErrorNotFound:
			status = http.StatusNotFound
		case model.FeatureErrorConflict:
			status = http.StatusConflict
		case model.FeatureErrorUnprocessable:
			status = http.StatusUnprocessableEntity
		}
		writeJSON(w, status, featureErr)
		return
	}
	writeJSON(w, http.StatusInternalServerError, model.FeaturePlatformError{Code: "INTERNAL_ERROR", Message: err.Error()})
}

func parsePositiveUintPath(w http.ResponseWriter, raw, name string) (uint64, bool) {
	value, err := strconv.ParseUint(raw, 10, 64)
	if err != nil || value == 0 {
		writeJSON(w, http.StatusBadRequest, model.FeaturePlatformError{Code: "INVALID_PATH_PARAMETER", Message: name + " must be a positive integer"})
		return 0, false
	}
	return value, true
}

func (c *FeatureController) SyncRegistry(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureRegistrySyncRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	response, err := c.Registry.Sync(r.Context(), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, response)
}

func (c *FeatureController) ListDefinitions(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	q := r.URL.Query()
	rows, total, err := c.Registry.List(r.Context(), q.Get("status"), q.Get("category"), q.Get("owner"), limit, offset)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": rows, "total": total, "limit": normalizedLimit(limit, 100, 500), "offset": maxInt(offset, 0)})
}

func (c *FeatureController) GetDefinition(w http.ResponseWriter, r *http.Request) {
	detail, err := c.Registry.Get(r.Context(), chi.URLParam(r, "feature_code"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

func (c *FeatureController) GetVersion(w http.ResponseWriter, r *http.Request) {
	id, ok := parsePositiveUintPath(w, chi.URLParam(r, "version_id"), "version_id")
	if !ok {
		return
	}
	detail, err := c.Registry.GetVersion(r.Context(), id)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

func (c *FeatureController) PublishVersion(w http.ResponseWriter, r *http.Request) {
	version, err := strconv.Atoi(chi.URLParam(r, "version"))
	if err != nil || version <= 0 {
		writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "version must be a positive integer"))
		return
	}
	if err := c.Registry.Publish(r.Context(), chi.URLParam(r, "feature_code"), version); err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "published", "version": version})
}

func (c *FeatureController) DeprecateVersion(w http.ResponseWriter, r *http.Request) {
	version, err := strconv.Atoi(chi.URLParam(r, "version"))
	if err != nil || version <= 0 {
		writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "version must be a positive integer"))
		return
	}
	if err := c.Registry.Deprecate(r.Context(), chi.URLParam(r, "feature_code"), version); err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "deprecated", "version": version})
}

func (c *FeatureController) Lineage(w http.ResponseWriter, r *http.Request) {
	response, err := c.Registry.Lineage(r.Context(), chi.URLParam(r, "feature_code"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, response)
}

func (c *FeatureController) Availability(w http.ResponseWriter, r *http.Request) {
	response, err := c.Registry.Availability(
		r.Context(), chi.URLParam(r, "feature_code"), r.URL.Query().Get("source_profile"),
	)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, response)
}

func (c *FeatureController) ReconcileStaleRuns(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureStaleRunReconcileRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	response, err := c.Runs.ReconcileStaleRuns(r.Context(), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, response)
}

func (c *FeatureController) CreateRun(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureRunCreateRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	response, err := c.Runs.CreateRun(r.Context(), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	status := http.StatusAccepted
	if response.Reused {
		status = http.StatusOK
	}
	writeJSON(w, status, response)
}

func (c *FeatureController) BatchSubjects(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureSubjectsBatchRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	count, err := c.Runs.BatchSubjects(r.Context(), chi.URLParam(r, "run_id"), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "inserted": count})
}

func (c *FeatureController) BatchItems(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureItemsBatchRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	count, err := c.Runs.BatchItems(r.Context(), chi.URLParam(r, "run_id"), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "inserted": count})
}

func (c *FeatureController) UpdateRun(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureStateUpdateRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	run, err := c.Runs.UpdateRun(r.Context(), chi.URLParam(r, "run_id"), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (c *FeatureController) UpdateItem(w http.ResponseWriter, r *http.Request) {
	versionID, ok := parsePositiveUintPath(w, chi.URLParam(r, "version_id"), "version_id")
	if !ok {
		return
	}
	var req model.FeatureRunItemUpdateRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	item, err := c.Runs.UpdateItem(r.Context(), chi.URLParam(r, "run_id"), versionID, req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (c *FeatureController) WriteNumericValues(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureNumericBatchRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	count, err := c.Runs.WriteNumericValues(r.Context(), chi.URLParam(r, "run_id"), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "inserted": count})
}

func (c *FeatureController) CompleteRun(w http.ResponseWriter, r *http.Request) {
	run, err := c.Runs.Complete(r.Context(), chi.URLParam(r, "run_id"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (c *FeatureController) FailRun(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ErrorCode    string `json:"error_code"`
		ErrorMessage string `json:"error_message"`
	}
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	run, err := c.Runs.Fail(r.Context(), chi.URLParam(r, "run_id"), req.ErrorCode, req.ErrorMessage)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (c *FeatureController) CancelRun(w http.ResponseWriter, r *http.Request) {
	run, err := c.Runs.Cancel(r.Context(), chi.URLParam(r, "run_id"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (c *FeatureController) ListRuns(w http.ResponseWriter, r *http.Request) {
	limit, offset := parseLimitOffset(r)
	q := r.URL.Query()
	var versionID uint64
	if raw := q.Get("feature_version_id"); raw != "" {
		parsed, err := strconv.ParseUint(raw, 10, 64)
		if err != nil || parsed == 0 {
			writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "feature_version_id must be positive"))
			return
		}
		versionID = parsed
	}
	rows, total, err := c.Runs.ListRuns(r.Context(), model.FeatureRunFilters{
		Status: q.Get("status"), ProducerService: q.Get("producer_service"),
		FeatureVersionID: versionID, BackfillID: q.Get("backfill_id"),
	}, limit, offset)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": rows, "total": total, "limit": normalizedLimit(limit, 100, 500), "offset": maxInt(offset, 0)})
}

func (c *FeatureController) GetRun(w http.ResponseWriter, r *http.Request) {
	includeSubjects := r.URL.Query().Get("include_subjects") == "true"
	detail, err := c.Runs.GetRun(r.Context(), chi.URLParam(r, "run_id"), includeSubjects)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

func (c *FeatureController) QueryNumericValues(w http.ResponseWriter, r *http.Request) {
	c.queryNumericValues(w, r, false)
}

func (c *FeatureController) QueryLatestNumericValues(w http.ResponseWriter, r *http.Request) {
	c.queryNumericValues(w, r, true)
}

func (c *FeatureController) QueryNumericCrossSection(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	observed, err := parseOptionalRFC3339(q.Get("observed_at"))
	if err != nil || observed == nil {
		writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "OBSERVED_AT_INVALID", "observed_at must be RFC3339"))
		return
	}
	query, ok := parseFeatureValueQuery(w, r, false)
	if !ok {
		return
	}
	query.ObservedFrom = observed
	query.ObservedTo = observed
	rows, total, err := c.Runs.QueryValues(r.Context(), query)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": rows, "total": total, "limit": query.Limit, "offset": query.Offset})
}

func (c *FeatureController) queryNumericValues(w http.ResponseWriter, r *http.Request, latest bool) {
	query, ok := parseFeatureValueQuery(w, r, latest)
	if !ok {
		return
	}
	rows, total, err := c.Runs.QueryValues(r.Context(), query)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": rows, "total": total, "limit": query.Limit, "offset": query.Offset})
}

func parseFeatureValueQuery(w http.ResponseWriter, r *http.Request, latest bool) (model.FeatureValueQuery, bool) {
	q := r.URL.Query()
	limit, offset := parseLimitOffset(r)
	query := model.FeatureValueQuery{FeatureCode: q.Get("feature_code"), RunID: q.Get("run_id"), Latest: latest, Limit: limit, Offset: offset}
	if raw := q.Get("version"); raw != "" {
		value, err := strconv.Atoi(raw)
		if err != nil || value <= 0 {
			writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "version must be positive"))
			return query, false
		}
		query.VersionNumber = value
	}
	if raw := q.Get("feature_version_id"); raw != "" {
		value, err := strconv.ParseUint(raw, 10, 64)
		if err != nil || value == 0 {
			writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "feature_version_id must be positive"))
			return query, false
		}
		query.FeatureVersionID = value
	}
	if q.Has("security_ids") {
		ids, err := parseUint64ListStrict(q.Get("security_ids"))
		if err != nil {
			writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "SECURITY_IDS_INVALID", "%s", err.Error()))
			return query, false
		}
		query.SecurityIDs = ids
	}
	var err error
	query.ObservedFrom, err = parseOptionalRFC3339(q.Get("observed_from"))
	if err != nil {
		writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "OBSERVED_FROM_INVALID", "%s", err.Error()))
		return query, false
	}
	query.ObservedTo, err = parseOptionalRFC3339(q.Get("observed_to"))
	if err != nil {
		writeFeatureError(w, model.NewFeatureError(model.FeatureErrorValidation, "OBSERVED_TO_INVALID", "%s", err.Error()))
		return query, false
	}
	return query, true
}

func parseOptionalRFC3339(raw string) (*time.Time, error) {
	if strings.TrimSpace(raw) == "" {
		return nil, nil
	}
	value, err := time.Parse(time.RFC3339Nano, raw)
	if err != nil {
		return nil, err
	}
	return &value, nil
}

func (c *FeatureController) CreateBackfill(w http.ResponseWriter, r *http.Request) {
	var req model.FeatureBackfillCreateRequest
	if !decodeFeatureJSON(w, r, &req) {
		return
	}
	job, runs, err := c.Runs.CreateBackfill(r.Context(), req)
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]any{"job": job, "runs": runs})
}

func (c *FeatureController) GetBackfill(w http.ResponseWriter, r *http.Request) {
	job, runs, err := c.Runs.GetBackfill(r.Context(), chi.URLParam(r, "backfill_id"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"job": job, "runs": runs})
}

func (c *FeatureController) RetryFailedBackfill(w http.ResponseWriter, r *http.Request) {
	runs, err := c.Runs.RetryFailedBackfill(r.Context(), chi.URLParam(r, "backfill_id"))
	if err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]any{"runs": runs, "count": len(runs)})
}

func (c *FeatureController) CancelBackfill(w http.ResponseWriter, r *http.Request) {
	if err := c.Runs.CancelBackfill(r.Context(), chi.URLParam(r, "backfill_id")); err != nil {
		writeFeatureError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled"})
}

func normalizedLimit(got, fallback, maximum int) int {
	if got <= 0 || got > maximum {
		return fallback
	}
	return got
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
