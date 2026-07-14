package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

var featureCodePattern = regexp.MustCompile(`^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$`)

type FeatureRegistryService struct {
	*core.BaseComponent
	Dao *dao.FeatureRegistryDao `infra:"dep:dao_feature_registry"`
}

func NewFeatureRegistryService() *FeatureRegistryService {
	return &FeatureRegistryService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_FEATURE_REGISTRY)}
}

func (s *FeatureRegistryService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *FeatureRegistryService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

func (s *FeatureRegistryService) Sync(ctx context.Context, req model.FeatureRegistrySyncRequest) (*model.FeatureRegistrySyncResponse, error) {
	if len(req.Manifests) == 0 {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "MANIFEST_REQUIRED", "at least one manifest is required")
	}
	response := &model.FeatureRegistrySyncResponse{
		Created:       []string{},
		UpdatedDrafts: []string{},
		Unchanged:     []string{},
		Rejected:      []model.FeatureSyncRejection{},
		GraphValid:    true,
	}
	seen := make(map[string]struct{}, len(req.Manifests))
	for i := range req.Manifests {
		manifest := req.Manifests[i]
		label := fmt.Sprintf("%s@%d", manifest.Feature.Code, manifest.Version.Number)
		if _, duplicate := seen[label]; duplicate {
			response.Rejected = append(response.Rejected, model.FeatureSyncRejection{
				Feature: label, Code: "MANIFEST_DUPLICATE", Error: "duplicate feature version in sync request",
			})
			continue
		}
		seen[label] = struct{}{}

		snapshot, err := normalizeAndValidateManifest(&manifest)
		if err != nil {
			response.Rejected = append(response.Rejected, rejectionFor(label, err))
			if featureErrorCode(err) == "DEPENDENCY_CYCLE" {
				response.GraphValid = false
			}
			continue
		}
		action, err := s.Dao.SyncManifest(ctx, manifest, snapshot)
		if err != nil {
			response.Rejected = append(response.Rejected, rejectionFor(label, err))
			if featureErrorCode(err) == "DEPENDENCY_CYCLE" {
				response.GraphValid = false
			}
			continue
		}
		switch action {
		case "created":
			response.Created = append(response.Created, label)
		case "updated_draft":
			response.UpdatedDrafts = append(response.UpdatedDrafts, label)
		case "unchanged":
			response.Unchanged = append(response.Unchanged, label)
		}
	}
	return response, nil
}

func rejectionFor(label string, err error) model.FeatureSyncRejection {
	return model.FeatureSyncRejection{Feature: label, Code: featureErrorCode(err), Error: err.Error()}
}

func featureErrorCode(err error) string {
	if typed, ok := err.(*model.FeaturePlatformError); ok {
		return typed.Code
	}
	return "INTERNAL_ERROR"
}

func normalizeAndValidateManifest(manifest *model.FeatureManifest) (model.JSONValue, error) {
	f := &manifest.Feature
	f.Code = strings.TrimSpace(f.Code)
	f.DisplayName = strings.TrimSpace(f.DisplayName)
	f.Kind = strings.TrimSpace(f.Kind)
	f.EntityType = strings.TrimSpace(f.EntityType)
	f.ValueType = strings.TrimSpace(f.ValueType)
	f.Unit = strings.TrimSpace(f.Unit)
	f.Category = strings.TrimSpace(f.Category)
	f.Owner = strings.TrimSpace(f.Owner)
	if !featureCodePattern.MatchString(f.Code) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_CODE_INVALID",
			"feature code %q must use at least three lowercase dot-separated segments", f.Code)
	}
	if f.DisplayName == "" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_DISPLAY_NAME_REQUIRED", "feature display_name is required")
	}
	if !containsString([]string{"raw", "metric", "factor", "signal", "prediction", "label"}, f.Kind) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_KIND_INVALID", "feature kind %q is invalid", f.Kind)
	}
	if f.EntityType == "" {
		f.EntityType = "security"
	}
	if f.EntityType != "security" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "ENTITY_TYPE_UNSUPPORTED", "entity_type %q is not supported", f.EntityType)
	}
	if !containsString([]string{"number", "integer", "boolean", "enum", "string", "json", "vector", "distribution"}, f.ValueType) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "VALUE_TYPE_INVALID", "value_type %q is invalid", f.ValueType)
	}
	if f.Tags == nil {
		f.Tags = []string{}
	}
	sort.Strings(f.Tags)

	v := &manifest.Version
	if v.Number <= 0 {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "version number must be positive")
	}
	if v.Status == "" {
		v.Status = "draft"
	}
	if v.Status != "draft" && v.Status != "published" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_STATUS_INVALID",
			"sync accepts only draft or published versions, got %q", v.Status)
	}
	if v.Frequency == "" {
		v.Frequency = "on_demand"
	}
	if v.AsOfSemantics == "" {
		v.AsOfSemantics = "snapshot"
	}
	if v.MissingPolicy == "" {
		v.MissingPolicy = "explicit_missing"
	}

	impl := &manifest.Implementation
	impl.Kind = strings.TrimSpace(impl.Kind)
	impl.ProducerService = strings.TrimSpace(impl.ProducerService)
	impl.Backend = strings.TrimSpace(impl.Backend)
	impl.Entrypoint = strings.TrimSpace(impl.Entrypoint)
	if !containsString([]string{"python", "expression", "vendor", "model", "llm", "external"}, impl.Kind) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "IMPLEMENTATION_KIND_INVALID", "implementation kind %q is invalid", impl.Kind)
	}
	if impl.ProducerService == "" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "PRODUCER_SERVICE_REQUIRED", "implementation producer_service is required")
	}
	if impl.ImplementationRevision <= 0 {
		impl.ImplementationRevision = 1
	}
	if impl.Config == nil {
		impl.Config = map[string]any{}
	}
	if key := findSensitiveConfigKey(impl.Config, ""); key != "" {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "SENSITIVE_CONFIG_FORBIDDEN",
			"manifest config must not contain sensitive key %s", key)
	}
	if impl.Status == "" {
		impl.Status = "active"
	}
	if !containsString([]string{"draft", "active", "disabled"}, impl.Status) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "IMPLEMENTATION_STATUS_INVALID", "implementation status %q is invalid", impl.Status)
	}
	if v.Status == "published" && impl.Status != "active" {
		return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "CANONICAL_IMPLEMENTATION_MISSING",
			"a published version requires an active implementation")
	}

	seenDependencies := make(map[string]struct{}, len(manifest.Dependencies))
	for i := range manifest.Dependencies {
		dep := &manifest.Dependencies[i]
		dep.Kind = strings.TrimSpace(dep.Kind)
		dep.FeatureCode = strings.TrimSpace(dep.FeatureCode)
		dep.Source = strings.TrimSpace(dep.Source)
		dep.Dataset = strings.TrimSpace(dep.Dataset)
		dep.DataType = strings.TrimSpace(dep.DataType)
		dep.RawField = strings.TrimSpace(dep.RawField)
		dep.ContractVersion = strings.TrimSpace(dep.ContractVersion)
		var key string
		switch dep.Kind {
		case "feature":
			if !featureCodePattern.MatchString(dep.FeatureCode) || dep.FeatureVersion <= 0 {
				return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_DEPENDENCY_INVALID",
					"feature dependency requires feature_code and a positive explicit feature_version")
			}
			if dep.FeatureCode == f.Code && dep.FeatureVersion == v.Number {
				return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "DEPENDENCY_SELF_REFERENCE", "feature version cannot depend on itself")
			}
			key = fmt.Sprintf("feature:%s@%d", dep.FeatureCode, dep.FeatureVersion)
		case "data_field":
			if dep.Source == "" || dep.Dataset == "" || dep.DataType == "" || dep.RawField == "" || dep.ContractVersion == "" {
				return nil, model.NewFeatureError(model.FeatureErrorValidation, "DATA_FIELD_DEPENDENCY_INVALID",
					"data_field dependency requires source, dataset, data_type, raw_field, and contract_version")
			}
			key = fmt.Sprintf("field:%s/%s/%s/%s@%s", dep.Source, dep.Dataset, dep.DataType, dep.RawField, dep.ContractVersion)
		default:
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "DEPENDENCY_KIND_INVALID", "dependency kind %q is invalid", dep.Kind)
		}
		if _, duplicate := seenDependencies[key]; duplicate {
			return nil, model.NewFeatureError(model.FeatureErrorValidation, "DEPENDENCY_DUPLICATE", "dependency %s is duplicated", key)
		}
		seenDependencies[key] = struct{}{}
	}

	if impl.Checksum == "" {
		impl.Checksum = checksumJSON(struct {
			Kind, ProducerService, Backend, Entrypoint string
			Revision                                   int
			Config                                     map[string]any
		}{impl.Kind, impl.ProducerService, impl.Backend, impl.Entrypoint, impl.ImplementationRevision, impl.Config})
	}
	if !isSHA256(impl.Checksum) {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "IMPLEMENTATION_CHECKSUM_INVALID", "implementation checksum must be a lowercase SHA-256 hex string")
	}

	// The checksum excludes its own field and therefore has a stable fixed point.
	providedManifestChecksum := v.ManifestChecksum
	v.ManifestChecksum = ""
	computedManifestChecksum := checksumJSON(manifest)
	if providedManifestChecksum != "" && providedManifestChecksum != computedManifestChecksum {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "MANIFEST_CHECKSUM_MISMATCH",
			"manifest_checksum does not match the canonical manifest content")
	}
	v.ManifestChecksum = computedManifestChecksum
	snapshot := model.NewJSONValue(manifest)
	return snapshot, nil
}

func checksumJSON(v any) string {
	b, _ := json.Marshal(v)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func isSHA256(value string) bool {
	if len(value) != 64 || strings.ToLower(value) != value {
		return false
	}
	_, err := hex.DecodeString(value)
	return err == nil
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func findSensitiveConfigKey(value any, path string) string {
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			lower := strings.ToLower(key)
			childPath := key
			if path != "" {
				childPath = path + "." + key
			}
			if !strings.HasSuffix(lower, "_ref") && (strings.Contains(lower, "password") || strings.Contains(lower, "secret") || strings.Contains(lower, "token") || strings.Contains(lower, "api_key") || lower == "dsn") {
				return childPath
			}
			if found := findSensitiveConfigKey(child, childPath); found != "" {
				return found
			}
		}
	case []any:
		for i, child := range typed {
			if found := findSensitiveConfigKey(child, fmt.Sprintf("%s[%d]", path, i)); found != "" {
				return found
			}
		}
	}
	return ""
}

func (s *FeatureRegistryService) Publish(ctx context.Context, featureCode string, version int) error {
	if !featureCodePattern.MatchString(featureCode) || version <= 0 {
		return model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_REFERENCE_INVALID", "feature code and positive version are required")
	}
	return s.Dao.Publish(ctx, featureCode, version)
}

func (s *FeatureRegistryService) Deprecate(ctx context.Context, featureCode string, version int) error {
	if !featureCodePattern.MatchString(featureCode) || version <= 0 {
		return model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_REFERENCE_INVALID", "feature code and positive version are required")
	}
	return s.Dao.Deprecate(ctx, featureCode, version)
}

func (s *FeatureRegistryService) List(ctx context.Context, status, category, owner string, limit, offset int) ([]model.FeatureDefinition, int64, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	if offset < 0 {
		offset = 0
	}
	return s.Dao.ListDefinitions(ctx, status, category, owner, limit, offset)
}

func (s *FeatureRegistryService) Get(ctx context.Context, featureCode string) (*model.FeatureDefinitionDetail, error) {
	return s.Dao.GetDefinitionDetail(ctx, featureCode)
}

func (s *FeatureRegistryService) GetVersion(ctx context.Context, versionID uint64) (*model.FeatureVersionSummary, error) {
	if versionID == 0 {
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_INVALID", "feature version id must be positive")
	}
	return s.Dao.GetVersionSummary(ctx, versionID)
}

func (s *FeatureRegistryService) Lineage(ctx context.Context, featureCode string) (*model.FeatureLineage, error) {
	return s.Dao.GetLineage(ctx, featureCode)
}

func (s *FeatureRegistryService) Availability(ctx context.Context, featureCode string) (*model.FeatureAvailability, error) {
	return s.Dao.GetAvailability(ctx, featureCode)
}
