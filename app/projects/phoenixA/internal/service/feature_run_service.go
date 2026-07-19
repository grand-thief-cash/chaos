package service

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type FeatureRunService struct {
	*core.BaseComponent
	Dao         *dao.FeatureRunDao      `infra:"dep:dao_feature_run"`
	RegistryDao *dao.FeatureRegistryDao `infra:"dep:dao_feature_registry"`
	Resolve     *ResolveCache           `infra:"dep:svc_resolve_cache"`
}

func NewFeatureRunService() *FeatureRunService {
	return &FeatureRunService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_FEATURE_RUN)}
}

func (s *FeatureRunService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *FeatureRunService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

func (s *FeatureRunService) CreateRun(ctx context.Context, req model.FeatureRunCreateRequest) (*model.FeatureRunCreateResponse, error) {
	if err := normalizeRunRequest(&req); err != nil {
		return nil, err
	}
	if err := s.RegistryDao.ValidatePublishedVersionIDs(ctx, req.RootFeatureVersionIDs); err != nil {
		return nil, err
	}
	if req.RetryOfRunID != nil {
		if !validUUID(*req.RetryOfRunID) {
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "RETRY_RUN_ID_INVALID", "retry_of_run_id must be a UUID")
		}
		if _, err := s.Dao.GetRun(ctx, *req.RetryOfRunID); err != nil {
			return nil, err
		}
	}
	payload := model.NewJSONValue(map[string]any{
		"root_feature_version_ids": req.RootFeatureVersionIDs,
		"dependency_plan_checksum": req.DependencyPlanChecksum,
		"parameters":               req.Parameters,
	})
	run := &model.FeatureRun{
		RunID:              req.RunID,
		RequestFingerprint: req.RequestFingerprint,
		ProducerService:    req.ProducerService,
		ProducerRunRef:     req.ProducerRunRef,
		TriggerType:        req.TriggerType,
		AsOfTime:           req.AsOfTime,
		DataCutoffTime:     req.DataCutoffTime,
		SourceProfile:      req.SourceProfile,
		Market:             req.Market,
		UniverseHash:       req.UniverseHash,
		RequestPayload:     payload,
		CodeRevision:       req.CodeRevision,
		Status:             "queued",
		RetryOfRunID:       req.RetryOfRunID,
	}
	created, reused, err := s.Dao.CreateOrReuse(ctx, run, req.Force)
	if err != nil {
		return nil, err
	}
	return &model.FeatureRunCreateResponse{
		Accepted: true, Reused: reused, RunID: created.RunID,
		Status: created.Status, RequestFingerprint: created.RequestFingerprint,
	}, nil
}

func normalizeRunRequest(req *model.FeatureRunCreateRequest) error {
	req.ProducerService = strings.TrimSpace(req.ProducerService)
	req.ProducerRunRef = strings.TrimSpace(req.ProducerRunRef)
	req.TriggerType = strings.TrimSpace(req.TriggerType)
	req.SourceProfile = strings.TrimSpace(req.SourceProfile)
	req.Market = strings.TrimSpace(req.Market)
	req.CodeRevision = strings.TrimSpace(req.CodeRevision)
	if req.RunID == "" {
		req.RunID = newUUID()
	} else if !validUUID(req.RunID) {
		return model.NewFeatureError(model.FeatureErrorValidation, "RUN_ID_INVALID", "run_id must be a UUID")
	}
	if req.ProducerService == "" || req.CodeRevision == "" {
		return model.NewFeatureError(model.FeatureErrorValidation, "RUN_CONTEXT_REQUIRED", "producer_service and code_revision are required")
	}
	if req.SourceProfile == "" {
		req.SourceProfile = "default"
	}
	if req.TriggerType == "" {
		req.TriggerType = "api"
	}
	if !containsString([]string{"manual", "cron", "api", "backfill"}, req.TriggerType) {
		return model.NewFeatureError(model.FeatureErrorValidation, "TRIGGER_TYPE_INVALID", "trigger_type %q is invalid", req.TriggerType)
	}
	if req.AsOfTime.IsZero() || req.DataCutoffTime.IsZero() {
		return model.NewFeatureError(model.FeatureErrorValidation, "RUN_TIME_REQUIRED", "as_of_time and data_cutoff_time are required")
	}
	if req.DataCutoffTime.After(req.AsOfTime) {
		return model.NewFeatureError(model.FeatureErrorValidation, "DATA_CUTOFF_VIOLATION", "data_cutoff_time must not be later than as_of_time")
	}
	if !isSHA256(req.UniverseHash) {
		return model.NewFeatureError(model.FeatureErrorValidation, "UNIVERSE_HASH_INVALID", "universe_hash must be a lowercase SHA-256 hex string")
	}
	if req.DependencyPlanChecksum != "" && !isSHA256(req.DependencyPlanChecksum) {
		return model.NewFeatureError(model.FeatureErrorValidation, "DEPENDENCY_PLAN_CHECKSUM_INVALID",
			"dependency_plan_checksum must be a lowercase SHA-256 hex string when provided")
	}
	if req.Parameters == nil {
		req.Parameters = map[string]any{}
	}
	sort.Slice(req.RootFeatureVersionIDs, func(i, j int) bool { return req.RootFeatureVersionIDs[i] < req.RootFeatureVersionIDs[j] })
	for i, id := range req.RootFeatureVersionIDs {
		if id == 0 || (i > 0 && id == req.RootFeatureVersionIDs[i-1]) {
			return model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "root_feature_version_ids must be unique positive ids")
		}
	}
	computedFingerprint := checksumJSON(struct {
		Versions               []uint64
		AsOf                   string
		Cutoff                 string
		SourceProfile          string
		Market                 string
		UniverseHash           string
		Parameters             map[string]any
		CodeRevision           string
		DependencyPlanChecksum string
	}{
		req.RootFeatureVersionIDs, req.AsOfTime.UTC().Format(time.RFC3339Nano),
		req.DataCutoffTime.UTC().Format(time.RFC3339Nano), req.SourceProfile,
		req.Market, req.UniverseHash, req.Parameters, req.CodeRevision, req.DependencyPlanChecksum,
	})
	if req.RequestFingerprint == "" {
		req.RequestFingerprint = computedFingerprint
	} else if req.RequestFingerprint != computedFingerprint {
		return model.NewFeatureError(model.FeatureErrorValidation, "REQUEST_FINGERPRINT_MISMATCH",
			"request_fingerprint does not match the canonical run context")
	}
	return nil
}

func (s *FeatureRunService) BatchSubjects(ctx context.Context, runID string, req model.FeatureSubjectsBatchRequest) (int, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return 0, err
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return 0, err
	}
	if run.Status != "queued" && run.Status != "planning" {
		return 0, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "subjects cannot be added while run %s is %s", runID, run.Status)
	}
	if len(req.SecurityIDs) == 0 {
		return 0, model.NewFeatureError(model.FeatureErrorValidation, "RUN_SUBJECT_REQUIRED", "security_ids must not be empty")
	}
	seen := make(map[uint64]struct{}, len(req.SecurityIDs))
	subjects := make([]model.FeatureRunSubject, 0, len(req.SecurityIDs))
	for _, id := range req.SecurityIDs {
		if id == 0 {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "INVALID_SUBJECT", "security_id must be positive")
		}
		if _, duplicate := seen[id]; duplicate {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "INVALID_SUBJECT", "security_id %d is duplicated", id)
		}
		seen[id] = struct{}{}
		security, found, err := s.Resolve.ResolveSecurity(ctx, id)
		if err != nil {
			return 0, fmt.Errorf("resolve security_id %d: %w", id, err)
		}
		if !found {
			return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "INVALID_SUBJECT", "security_id %d does not exist", id)
		}
		subjects = append(subjects, model.FeatureRunSubject{
			RunID: runID, SecurityID: id, SymbolSnapshot: security.Symbol,
			Exchange: security.Exchange, AssetType: security.AssetType, IncludedReason: req.IncludedReason,
		})
	}
	return s.Dao.BatchSubjects(ctx, runID, subjects)
}

func (s *FeatureRunService) BatchItems(ctx context.Context, runID string, req model.FeatureItemsBatchRequest) (int, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return 0, err
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return 0, err
	}
	if run.Status != "queued" && run.Status != "planning" {
		return 0, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "items cannot be added while run %s is %s", runID, run.Status)
	}
	sort.Slice(req.FeatureVersionIDs, func(i, j int) bool { return req.FeatureVersionIDs[i] < req.FeatureVersionIDs[j] })
	for i, id := range req.FeatureVersionIDs {
		if id == 0 || (i > 0 && id == req.FeatureVersionIDs[i-1]) {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "feature_version_ids must be unique positive ids")
		}
	}
	if err := s.RegistryDao.ValidatePublishedVersionIDs(ctx, req.FeatureVersionIDs); err != nil {
		return 0, err
	}
	var payload struct {
		RootFeatureVersionIDs []uint64 `json:"root_feature_version_ids"`
	}
	if err := json.Unmarshal(run.RequestPayload, &payload); err != nil || len(payload.RootFeatureVersionIDs) == 0 {
		return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "RUN_PAYLOAD_INVALID",
			"run %s does not contain a valid frozen root feature set", runID)
	}
	expected, err := s.RegistryDao.ResolveExecutionVersionIDs(ctx, payload.RootFeatureVersionIDs)
	if err != nil {
		return 0, err
	}
	if !equalUint64Slices(expected, req.FeatureVersionIDs) {
		return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "RUN_ITEM_PLAN_MISMATCH",
			"feature_version_ids must exactly match the frozen dependency closure %v", expected)
	}
	return s.Dao.BatchItems(ctx, runID, req.FeatureVersionIDs)
}

func equalUint64Slices(left, right []uint64) bool {
	if len(left) != len(right) {
		return false
	}
	for i := range left {
		if left[i] != right[i] {
			return false
		}
	}
	return true
}

var runTransitions = map[string]map[string]bool{
	"queued":     {"planning": true, "cancelled": true, "aborted": true},
	"planning":   {"running": true, "failed": true, "cancelled": true, "aborted": true},
	"running":    {"validating": true, "failed": true, "cancelled": true, "aborted": true},
	"validating": {"succeeded": true, "partially_succeeded": true, "failed": true, "aborted": true},
}

var itemTransitions = map[string]map[string]bool{
	"queued":     {"running": true, "skipped": true},
	"running":    {"validating": true, "failed": true, "skipped": true},
	"validating": {"succeeded": true, "failed": true},
}

func validTransition(transitions map[string]map[string]bool, from, to string) bool {
	return transitions[from] != nil && transitions[from][to]
}

func validRunStateUpdate(req model.FeatureStateUpdateRequest) bool {
	if req.ExpectedStatus == req.NewStatus && req.HeartbeatAt != nil {
		return containsString([]string{"planning", "running", "validating"}, req.ExpectedStatus)
	}
	return validTransition(runTransitions, req.ExpectedStatus, req.NewStatus)
}

func (s *FeatureRunService) UpdateRun(ctx context.Context, runID string, req model.FeatureStateUpdateRequest) (*model.FeatureRun, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	if !validRunStateUpdate(req) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "RUN_TRANSITION_INVALID",
			"run transition %s -> %s is not allowed", req.ExpectedStatus, req.NewStatus)
	}
	if req.HeartbeatAt != nil {
		if req.HeartbeatAt.IsZero() || req.HeartbeatAt.After(time.Now().UTC().Add(time.Minute)) {
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "RUN_HEARTBEAT_INVALID",
				"heartbeat_at must be a non-zero time no more than one minute in the future")
		}
	}
	updates := map[string]any{}
	if req.WorkerID != "" {
		updates["worker_id"] = req.WorkerID
	}
	if req.ErrorCode != "" || req.ErrorMessage != "" {
		updates["error_code"] = req.ErrorCode
		updates["error_message"] = req.ErrorMessage
	}
	if req.HeartbeatAt != nil {
		updates["heartbeat_at"] = *req.HeartbeatAt
	}
	if req.ExpectedStatus == "planning" && req.NewStatus == "running" {
		current, err := s.Dao.GetRun(ctx, runID)
		if err != nil {
			return nil, err
		}
		if current.Status != req.ExpectedStatus {
			return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT",
				"run %s is not in expected status %s", runID, req.ExpectedStatus)
		}
		subjects, items, err := s.Dao.RunPreparationCounts(ctx, runID)
		if err != nil {
			return nil, err
		}
		if subjects == 0 || items == 0 {
			return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "RUN_NOT_PREPARED",
				"run %s requires frozen subjects and dependency-closed items before execution", runID)
		}
	}
	run, err := s.Dao.UpdateRunStatus(ctx, runID, req.ExpectedStatus, req.NewStatus, updates)
	if err == nil && run.BackfillID != nil {
		err = s.Dao.RefreshBackfillCounts(ctx, *run.BackfillID)
	}
	return run, err
}

func (s *FeatureRunService) UpdateItem(ctx context.Context, runID string, versionID uint64, req model.FeatureRunItemUpdateRequest) (*model.FeatureRunItem, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	if !validTransition(itemTransitions, req.ExpectedStatus, req.NewStatus) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "RUN_ITEM_TRANSITION_INVALID",
			"run item transition %s -> %s is not allowed", req.ExpectedStatus, req.NewStatus)
	}
	if req.InputCount < 0 || req.OutputCount < 0 || req.ValidCount < 0 || req.MissingCount < 0 || req.InvalidCount < 0 || req.DurationMS < 0 {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "RUN_ITEM_COUNTS_INVALID", "run item counts and duration must not be negative")
	}
	if req.QualitySummary == nil {
		req.QualitySummary = map[string]any{}
	}
	req.QualitySummary = normalizeItemQualitySummary(req)
	updates := map[string]any{
		"input_count": req.InputCount, "output_count": req.OutputCount,
		"valid_count": req.ValidCount, "missing_count": req.MissingCount,
		"invalid_count": req.InvalidCount, "duration_ms": req.DurationMS,
		"quality_summary": model.NewJSONValue(req.QualitySummary),
		"error_code":      req.ErrorCode, "error_message": req.ErrorMessage,
	}
	return s.Dao.UpdateItemStatus(ctx, runID, versionID, req.ExpectedStatus, req.NewStatus, updates)
}

func normalizeItemQualitySummary(req model.FeatureRunItemUpdateRequest) map[string]any {
	summary := make(map[string]any, len(req.QualitySummary)+8)
	for key, value := range req.QualitySummary {
		summary[key] = value
	}
	summary["status"] = req.NewStatus
	summary["input_count"] = req.InputCount
	summary["output_count"] = req.OutputCount
	summary["valid_count"] = req.ValidCount
	summary["missing_count"] = req.MissingCount
	summary["invalid_count"] = req.InvalidCount
	if req.InputCount > 0 {
		summary["coverage_ratio"] = float64(req.ValidCount) / float64(req.InputCount)
		summary["output_ratio"] = float64(req.OutputCount) / float64(req.InputCount)
	} else {
		summary["coverage_ratio"] = float64(0)
		summary["output_ratio"] = float64(0)
	}
	gatePassed := req.NewStatus == "succeeded" || req.NewStatus == "validating"
	summary["gate_passed"] = gatePassed
	if req.ErrorCode != "" {
		summary["error_code"] = req.ErrorCode
	}
	return summary
}

func (s *FeatureRunService) ReconcileStaleRuns(ctx context.Context, req model.FeatureStaleRunReconcileRequest) (*model.FeatureStaleRunReconcileResponse, error) {
	req.ProducerService = strings.TrimSpace(req.ProducerService)
	if req.ProducerService == "" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "PRODUCER_SERVICE_REQUIRED",
			"producer_service is required")
	}
	now := time.Now().UTC()
	if req.StaleBefore.IsZero() || !req.StaleBefore.Before(now) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "STALE_BEFORE_INVALID",
			"stale_before must be a time in the past")
	}
	runs, err := s.Dao.AbortStaleRuns(ctx, req.ProducerService, req.StaleBefore.UTC())
	if err != nil {
		return nil, err
	}
	runIDs := make([]string, 0, len(runs))
	backfills := make(map[string]struct{})
	for _, run := range runs {
		runIDs = append(runIDs, run.RunID)
		if run.BackfillID != nil {
			backfills[*run.BackfillID] = struct{}{}
		}
	}
	for backfillID := range backfills {
		if err := s.Dao.RefreshBackfillCounts(ctx, backfillID); err != nil {
			return nil, err
		}
	}
	return &model.FeatureStaleRunReconcileResponse{
		StaleBefore: req.StaleBefore.UTC(), AbortedCount: len(runIDs), RunIDs: runIDs,
	}, nil
}

func (s *FeatureRunService) WriteNumericValues(ctx context.Context, runID string, req model.FeatureNumericBatchRequest) (int, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return 0, err
	}
	if len(req.Values) == 0 || len(req.Values) > 5000 {
		return 0, model.NewFeatureError(model.FeatureErrorValidation, "VALUE_BATCH_SIZE_INVALID", "numeric batch must contain 1 to 5000 values")
	}
	if req.FeatureVersionID == 0 || req.ObservedAt.IsZero() {
		return 0, model.NewFeatureError(model.FeatureErrorValidation, "VALUE_CONTEXT_REQUIRED", "feature_version_id and observed_at are required")
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return 0, err
	}
	if run.Status != "running" && run.Status != "validating" {
		return 0, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "values cannot be written while run %s is %s", runID, run.Status)
	}
	if !req.ObservedAt.Equal(run.AsOfTime) {
		return 0, model.NewFeatureError(model.FeatureErrorValidation, "OBSERVED_AT_MISMATCH", "Phase 1 requires observed_at to equal run as_of_time")
	}
	item, err := s.Dao.GetRunItem(ctx, runID, req.FeatureVersionID)
	if err != nil {
		return 0, err
	}
	if item.Status != "running" && item.Status != "validating" {
		return 0, model.NewFeatureError(model.FeatureErrorConflict, "RUN_ITEM_STATE_CONFLICT",
			"values cannot be written while run item %s/%d is %s", runID, req.FeatureVersionID, item.Status)
	}
	subjects, err := s.Dao.SubjectIDSet(ctx, runID)
	if err != nil {
		return 0, err
	}
	requiresAvailability, err := s.RegistryDao.VersionRequiresSourceAvailability(ctx, req.FeatureVersionID)
	if err != nil {
		return 0, err
	}
	seen := make(map[uint64]struct{}, len(req.Values))
	rows := make([]model.FeatureNumericValue, 0, len(req.Values))
	for _, input := range req.Values {
		if _, ok := subjects[input.SecurityID]; !ok {
			return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "OUTPUT_OUTSIDE_UNIVERSE",
				"security_id %d is not in run %s subjects", input.SecurityID, runID)
		}
		if _, duplicate := seen[input.SecurityID]; duplicate {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "OUTPUT_DUPLICATE_SUBJECT", "security_id %d is duplicated in numeric batch", input.SecurityID)
		}
		seen[input.SecurityID] = struct{}{}
		if !containsString([]string{"valid", "missing", "invalid"}, input.ValueStatus) {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "VALUE_STATUS_INVALID", "value_status %q is invalid", input.ValueStatus)
		}
		if input.ValueStatus == "valid" {
			if input.Value == nil || math.IsNaN(*input.Value) || math.IsInf(*input.Value, 0) {
				return 0, model.NewFeatureError(model.FeatureErrorValidation, "OUTPUT_NAN_OR_INFINITE", "valid value for security_id %d must be finite", input.SecurityID)
			}
		} else if input.Value != nil {
			return 0, model.NewFeatureError(model.FeatureErrorValidation, "VALUE_STATUS_MISMATCH", "%s value for security_id %d must be null", input.ValueStatus, input.SecurityID)
		}
		if requiresAvailability && input.SourceMaxAvailableAt == nil {
			return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "SOURCE_AVAILABILITY_REQUIRED",
				"feature version %d depends on source data and requires source_max_available_at", req.FeatureVersionID)
		}
		if input.SourceMaxAvailableAt != nil && input.SourceMaxAvailableAt.After(run.DataCutoffTime) {
			return 0, model.NewFeatureError(model.FeatureErrorUnprocessable, "DATA_CUTOFF_VIOLATION",
				"source_max_available_at for security_id %d exceeds run data_cutoff_time", input.SecurityID)
		}
		if input.QualityFlags == nil {
			input.QualityFlags = map[string]any{}
		}
		rows = append(rows, model.FeatureNumericValue{
			RunID: runID, FeatureVersionID: req.FeatureVersionID, SecurityID: input.SecurityID,
			ObservedAt: req.ObservedAt, Value: input.Value, ValueStatus: input.ValueStatus,
			QualityFlags: model.NewJSONValue(input.QualityFlags), SourceMaxAvailableAt: input.SourceMaxAvailableAt,
			ComputedAt: time.Now().UTC(),
		})
	}
	return s.Dao.WriteNumericValues(ctx, rows)
}

func (s *FeatureRunService) Complete(ctx context.Context, runID string) (*model.FeatureRun, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return nil, err
	}
	if run.Status != "validating" {
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "run %s is %s, expected validating", runID, run.Status)
	}
	items, err := s.Dao.ListRunItems(ctx, runID)
	if err != nil {
		return nil, err
	}
	if len(items) == 0 {
		return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "RUN_ITEM_REQUIRED", "run %s has no items", runID)
	}
	succeeded, failed := 0, 0
	for _, item := range items {
		if !dao.IsTerminalItemStatus(item.Status) {
			return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_ITEM_NOT_TERMINAL",
				"run item %s/%d is still %s", runID, item.FeatureVersionID, item.Status)
		}
		if item.Status == "succeeded" {
			succeeded++
		} else {
			failed++
		}
	}
	next := "failed"
	if succeeded == len(items) {
		next = "succeeded"
	} else if succeeded > 0 && failed > 0 {
		next = "partially_succeeded"
	}
	return s.UpdateRun(ctx, runID, model.FeatureStateUpdateRequest{ExpectedStatus: "validating", NewStatus: next})
}

func (s *FeatureRunService) Fail(ctx context.Context, runID, code, message string) (*model.FeatureRun, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return nil, err
	}
	if run.Status != "planning" && run.Status != "running" && run.Status != "validating" {
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "run %s cannot fail from %s", runID, run.Status)
	}
	return s.UpdateRun(ctx, runID, model.FeatureStateUpdateRequest{
		ExpectedStatus: run.Status, NewStatus: "failed", ErrorCode: code, ErrorMessage: message,
	})
}

func (s *FeatureRunService) Cancel(ctx context.Context, runID string) (*model.FeatureRun, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	run, err := s.Dao.GetRun(ctx, runID)
	if err != nil {
		return nil, err
	}
	if run.Status != "queued" && run.Status != "planning" && run.Status != "running" {
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT", "run %s cannot be cancelled from %s", runID, run.Status)
	}
	return s.UpdateRun(ctx, runID, model.FeatureStateUpdateRequest{ExpectedStatus: run.Status, NewStatus: "cancelled"})
}

func (s *FeatureRunService) ListRuns(ctx context.Context, f model.FeatureRunFilters, limit, offset int) ([]model.FeatureRun, int64, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	if offset < 0 {
		offset = 0
	}
	return s.Dao.ListRuns(ctx, f, limit, offset)
}

func (s *FeatureRunService) GetRun(ctx context.Context, runID string, includeSubjects bool) (*model.FeatureRunDetail, error) {
	if err := validateFeatureRunID(runID); err != nil {
		return nil, err
	}
	return s.Dao.GetRunDetail(ctx, runID, includeSubjects)
}

func (s *FeatureRunService) QueryValues(ctx context.Context, q model.FeatureValueQuery) ([]model.FeatureNumericValue, int64, error) {
	if q.FeatureVersionID == 0 && q.FeatureCode == "" {
		return nil, 0, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_REFERENCE_REQUIRED", "feature_code or feature_version_id is required")
	}
	if q.RunID != "" && !validUUID(q.RunID) {
		return nil, 0, model.NewFeatureError(model.FeatureErrorValidation, "RUN_ID_INVALID", "run_id must be a UUID")
	}
	if q.ObservedFrom != nil && q.ObservedTo != nil && q.ObservedFrom.After(*q.ObservedTo) {
		return nil, 0, model.NewFeatureError(model.FeatureErrorValidation, "OBSERVED_RANGE_INVALID", "observed_from must not be later than observed_to")
	}
	if q.Limit <= 0 || q.Limit > 5000 {
		q.Limit = 500
	}
	return s.Dao.QueryValues(ctx, q)
}

func (s *FeatureRunService) CreateBackfill(ctx context.Context, req model.FeatureBackfillCreateRequest) (*model.FeatureBackfillJob, []model.FeatureRun, error) {
	req.Step = strings.TrimSpace(req.Step)
	req.CalendarCode = strings.TrimSpace(req.CalendarCode)
	req.SourceProfile = strings.TrimSpace(req.SourceProfile)
	req.Market = strings.TrimSpace(req.Market)
	req.ProducerService = strings.TrimSpace(req.ProducerService)
	req.CodeRevision = strings.TrimSpace(req.CodeRevision)
	if req.CalendarCode != "" {
		return nil, nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "BACKFILL_CALENDAR_UNSUPPORTED",
			"calendar_code is reserved until a governed trading calendar is available; use explicit_as_of_times for trading dates")
	}
	sort.Slice(req.RootFeatureVersionIDs, func(i, j int) bool { return req.RootFeatureVersionIDs[i] < req.RootFeatureVersionIDs[j] })
	for i, id := range req.RootFeatureVersionIDs {
		if id == 0 || (i > 0 && id == req.RootFeatureVersionIDs[i-1]) {
			return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID",
				"root_feature_version_ids must be unique positive ids")
		}
	}
	if err := s.RegistryDao.ValidatePublishedVersionIDs(ctx, req.RootFeatureVersionIDs); err != nil {
		return nil, nil, err
	}
	times, err := expandBackfillTimes(req)
	if err != nil {
		return nil, nil, err
	}
	if req.ProducerService == "" || req.CodeRevision == "" || !isSHA256(req.UniverseHash) {
		return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CONTEXT_INVALID",
			"producer_service, code_revision, and a SHA-256 universe_hash are required")
	}
	if req.DependencyPlanChecksum != "" && !isSHA256(req.DependencyPlanChecksum) {
		return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "DEPENDENCY_PLAN_CHECKSUM_INVALID",
			"dependency_plan_checksum must be a lowercase SHA-256 hex string when provided")
	}
	if req.SourceProfile == "" {
		req.SourceProfile = "default"
	}
	if req.MaxConcurrency <= 0 {
		req.MaxConcurrency = 1
	}
	if req.DataCutoffPolicy == nil {
		req.DataCutoffPolicy = map[string]any{"mode": "same_as_as_of"}
	}
	if req.UniverseRequest == nil {
		req.UniverseRequest = map[string]any{}
	}
	backfillID := newUUID()
	expandedStrings := make([]string, len(times))
	rootIDs := make(model.Int64Array, len(req.RootFeatureVersionIDs))
	for i, id := range req.RootFeatureVersionIDs {
		rootIDs[i] = int64(id)
	}
	job := &model.FeatureBackfillJob{
		BackfillID: backfillID, RootFeatureVersionIDs: rootIDs,
		StartAsOf: req.StartAsOf, EndAsOf: req.EndAsOf, Step: req.Step,
		CalendarCode: req.CalendarCode, DataCutoffPolicy: model.NewJSONValue(req.DataCutoffPolicy),
		SourceProfile: req.SourceProfile, Market: req.Market,
		UniverseRequest: model.NewJSONValue(req.UniverseRequest), MaxConcurrency: req.MaxConcurrency,
		Status: "queued", TotalCount: len(times),
	}
	runs := make([]model.FeatureRun, 0, len(times))
	for i, asOf := range times {
		expandedStrings[i] = asOf.UTC().Format(time.RFC3339Nano)
		cutoff, err := backfillCutoff(req.DataCutoffPolicy, asOf)
		if err != nil {
			return nil, nil, err
		}
		attempt := 1
		sequence := i
		payload := map[string]any{"root_feature_version_ids": req.RootFeatureVersionIDs, "dependency_plan_checksum": req.DependencyPlanChecksum, "backfill_id": backfillID, "backfill_sequence": i}
		fingerprint := checksumJSON(map[string]any{
			"versions": req.RootFeatureVersionIDs, "as_of": asOf.UTC().Format(time.RFC3339Nano),
			"cutoff": cutoff.UTC().Format(time.RFC3339Nano), "source_profile": req.SourceProfile,
			"market": req.Market, "universe_hash": req.UniverseHash, "code_revision": req.CodeRevision,
			"dependency_plan_checksum": req.DependencyPlanChecksum,
		})
		runs = append(runs, model.FeatureRun{
			RunID: newUUID(), RequestFingerprint: fingerprint, ProducerService: req.ProducerService,
			TriggerType: "backfill", AsOfTime: asOf, DataCutoffTime: cutoff,
			SourceProfile: req.SourceProfile, Market: req.Market, UniverseHash: req.UniverseHash,
			RequestPayload: model.NewJSONValue(payload), CodeRevision: req.CodeRevision, Status: "queued",
			BackfillID: &backfillID, BackfillSequence: &sequence, BackfillAttempt: &attempt,
		})
	}
	job.ExpandedAsOfTimes = model.NewJSONValue(expandedStrings)
	if err := s.Dao.CreateBackfill(ctx, job, runs); err != nil {
		return nil, nil, err
	}
	return job, runs, nil
}

func expandBackfillTimes(req model.FeatureBackfillCreateRequest) ([]time.Time, error) {
	if req.StartAsOf.IsZero() || req.EndAsOf.IsZero() || req.StartAsOf.After(req.EndAsOf) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_RANGE_INVALID", "start_as_of and end_as_of must define a non-empty ascending range")
	}
	if req.Step == "explicit" {
		if len(req.ExplicitAsOfTimes) == 0 {
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_TIMES_REQUIRED", "explicit step requires explicit_as_of_times")
		}
		times := append([]time.Time(nil), req.ExplicitAsOfTimes...)
		sort.Slice(times, func(i, j int) bool { return times[i].Before(times[j]) })
		for i, value := range times {
			if value.Before(req.StartAsOf) || value.After(req.EndAsOf) || (i > 0 && value.Equal(times[i-1])) {
				return nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_TIMES_INVALID", "explicit times must be unique and within the requested range")
			}
		}
		return times, nil
	}
	if !containsString([]string{"daily", "weekly", "monthly", "quarterly"}, req.Step) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_STEP_INVALID", "step %q is invalid", req.Step)
	}
	result := make([]time.Time, 0)
	for i := 0; ; i++ {
		var current time.Time
		switch req.Step {
		case "daily":
			current = req.StartAsOf.AddDate(0, 0, i)
		case "weekly":
			current = req.StartAsOf.AddDate(0, 0, 7*i)
		case "monthly":
			current = addMonthsClamped(req.StartAsOf, i)
		case "quarterly":
			current = addMonthsClamped(req.StartAsOf, 3*i)
		}
		if current.After(req.EndAsOf) {
			break
		}
		result = append(result, current)
		if len(result) > 10000 {
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_TOO_LARGE", "backfill expands to more than 10000 dates")
		}
	}
	return result, nil
}

func addMonthsClamped(base time.Time, months int) time.Time {
	year, month, day := base.Date()
	targetFirst := time.Date(year, month+time.Month(months), 1, base.Hour(), base.Minute(), base.Second(), base.Nanosecond(), base.Location())
	lastDay := time.Date(targetFirst.Year(), targetFirst.Month()+1, 0, base.Hour(), base.Minute(), base.Second(), base.Nanosecond(), base.Location()).Day()
	if day > lastDay {
		day = lastDay
	}
	return time.Date(targetFirst.Year(), targetFirst.Month(), day, base.Hour(), base.Minute(), base.Second(), base.Nanosecond(), base.Location())
}

func backfillCutoff(policy map[string]any, asOf time.Time) (time.Time, error) {
	mode, _ := policy["mode"].(string)
	if mode == "" || mode == "same_as_as_of" {
		return asOf, nil
	}
	if mode == "lag_seconds" {
		lag, ok := numericPolicyValue(policy["seconds"])
		if !ok || lag < 0 {
			return time.Time{}, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CUTOFF_POLICY_INVALID", "lag_seconds policy requires non-negative numeric seconds")
		}
		return asOf.Add(-time.Duration(lag * float64(time.Second))), nil
	}
	if mode == "explicit" {
		values, ok := policy["values"].(map[string]any)
		if !ok {
			return time.Time{}, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CUTOFF_POLICY_INVALID", "explicit cutoff policy requires values map")
		}
		raw, ok := values[asOf.UTC().Format(time.RFC3339Nano)].(string)
		if !ok {
			return time.Time{}, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CUTOFF_MISSING", "explicit cutoff is missing for %s", asOf.Format(time.RFC3339Nano))
		}
		cutoff, err := time.Parse(time.RFC3339Nano, raw)
		if err != nil || cutoff.After(asOf) {
			return time.Time{}, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CUTOFF_POLICY_INVALID", "explicit cutoff for %s is invalid or later than as_of", asOf.Format(time.RFC3339Nano))
		}
		return cutoff, nil
	}
	return time.Time{}, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_CUTOFF_POLICY_INVALID", "cutoff policy mode %q is invalid", mode)
}

func numericPolicyValue(value any) (float64, bool) {
	switch typed := value.(type) {
	case float64:
		return typed, true
	case float32:
		return float64(typed), true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case uint64:
		return float64(typed), true
	default:
		return 0, false
	}
}

func (s *FeatureRunService) GetBackfill(ctx context.Context, backfillID string) (*model.FeatureBackfillJob, []model.FeatureRun, error) {
	if !validUUID(backfillID) {
		return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_ID_INVALID", "backfill_id must be a UUID")
	}
	return s.Dao.GetBackfill(ctx, backfillID)
}

func (s *FeatureRunService) RetryFailedBackfill(ctx context.Context, backfillID string) ([]model.FeatureRun, error) {
	job, runs, err := s.GetBackfill(ctx, backfillID)
	if err != nil {
		return nil, err
	}
	if job.Status == "cancelled" {
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "BACKFILL_STATE_CONFLICT", "cancelled backfill cannot be retried")
	}
	latest := dao.LatestBackfillRuns(runs)
	retries := make([]model.FeatureRun, 0)
	for _, old := range latest {
		if old.Status != "failed" && old.Status != "aborted" {
			continue
		}
		attempt := 1
		if old.BackfillAttempt != nil {
			attempt = *old.BackfillAttempt + 1
		}
		retryID := old.RunID
		copy := old
		copy.RunID = newUUID()
		copy.Status = "queued"
		copy.RetryOfRunID = &retryID
		copy.BackfillAttempt = &attempt
		copy.WorkerID = ""
		copy.HeartbeatAt = nil
		copy.StartedAt = nil
		copy.FinishedAt = nil
		copy.ErrorCode = ""
		copy.ErrorMessage = ""
		copy.CreatedAt = time.Time{}
		copy.UpdatedAt = time.Time{}
		retries = append(retries, copy)
	}
	if len(retries) == 0 {
		return []model.FeatureRun{}, nil
	}
	inserted, err := s.Dao.CreateBackfillRetries(ctx, backfillID, retries)
	if err != nil {
		return nil, err
	}
	if err := s.Dao.RefreshBackfillCounts(ctx, backfillID); err != nil {
		return nil, err
	}
	return inserted, nil
}

func (s *FeatureRunService) CancelBackfill(ctx context.Context, backfillID string) error {
	if !validUUID(backfillID) {
		return model.NewFeatureError(model.FeatureErrorValidation, "BACKFILL_ID_INVALID", "backfill_id must be a UUID")
	}
	return s.Dao.SetBackfillCancelled(ctx, backfillID)
}

func newUUID() string {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		panic(fmt.Sprintf("generate UUID: %v", err))
	}
	raw[6] = (raw[6] & 0x0f) | 0x40
	raw[8] = (raw[8] & 0x3f) | 0x80
	return fmt.Sprintf("%s-%s-%s-%s-%s",
		hex.EncodeToString(raw[0:4]), hex.EncodeToString(raw[4:6]), hex.EncodeToString(raw[6:8]),
		hex.EncodeToString(raw[8:10]), hex.EncodeToString(raw[10:16]))
}

func validUUID(value string) bool {
	if len(value) != 36 || value[8] != '-' || value[13] != '-' || value[18] != '-' || value[23] != '-' {
		return false
	}
	_, err := hex.DecodeString(strings.ReplaceAll(value, "-", ""))
	return err == nil
}

func validateFeatureRunID(runID string) error {
	if !validUUID(runID) {
		return model.NewFeatureError(model.FeatureErrorValidation, "RUN_ID_INVALID", "run_id must be a UUID")
	}
	return nil
}
