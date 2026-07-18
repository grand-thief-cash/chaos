package model

import (
	"database/sql/driver"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	FeatureErrorValidation    = "validation"
	FeatureErrorNotFound      = "not_found"
	FeatureErrorConflict      = "conflict"
	FeatureErrorUnprocessable = "unprocessable"
)

type FeaturePlatformError struct {
	Kind    string `json:"-"`
	Code    string `json:"code"`
	Message string `json:"error"`
}

func (e *FeaturePlatformError) Error() string { return e.Message }

func NewFeatureError(kind, code, format string, args ...any) *FeaturePlatformError {
	return &FeaturePlatformError{Kind: kind, Code: code, Message: fmt.Sprintf(format, args...)}
}

// JSONValue is a PostgreSQL JSONB value that preserves arbitrary JSON shapes.
type JSONValue []byte

func NewJSONValue(v any) JSONValue {
	b, err := json.Marshal(v)
	if err != nil {
		return JSONValue(`{}`)
	}
	return JSONValue(b)
}

func (j JSONValue) Value() (driver.Value, error) {
	if len(j) == 0 {
		return "{}", nil
	}
	if !json.Valid(j) {
		return nil, fmt.Errorf("invalid JSON value")
	}
	return string(j), nil
}

func (j *JSONValue) Scan(src any) error {
	if src == nil {
		*j = JSONValue(`{}`)
		return nil
	}
	var data []byte
	switch v := src.(type) {
	case []byte:
		data = v
	case string:
		data = []byte(v)
	default:
		return fmt.Errorf("unsupported type for JSONValue: %T", src)
	}
	if !json.Valid(data) {
		return fmt.Errorf("invalid JSON from database")
	}
	*j = append((*j)[:0], data...)
	return nil
}

func (j JSONValue) MarshalJSON() ([]byte, error) {
	if len(j) == 0 {
		return []byte("{}"), nil
	}
	if !json.Valid(j) {
		return nil, fmt.Errorf("invalid JSON value")
	}
	return j, nil
}

func (j *JSONValue) UnmarshalJSON(data []byte) error {
	if !json.Valid(data) {
		return fmt.Errorf("invalid JSON value")
	}
	*j = append((*j)[:0], data...)
	return nil
}

// Int64Array maps a PostgreSQL BIGINT[] to a Go slice.
type Int64Array []int64

func (a Int64Array) Value() (driver.Value, error) {
	parts := make([]string, len(a))
	for i, v := range a {
		parts[i] = strconv.FormatInt(v, 10)
	}
	return "{" + strings.Join(parts, ",") + "}", nil
}

func (a *Int64Array) Scan(src any) error {
	if src == nil {
		*a = Int64Array{}
		return nil
	}
	var raw string
	switch v := src.(type) {
	case []byte:
		raw = string(v)
	case string:
		raw = v
	default:
		return fmt.Errorf("unsupported type for Int64Array: %T", src)
	}
	raw = strings.TrimSpace(raw)
	if raw == "" || raw == "{}" {
		*a = Int64Array{}
		return nil
	}
	raw = strings.TrimPrefix(strings.TrimSuffix(raw, "}"), "{")
	parts := strings.Split(raw, ",")
	out := make(Int64Array, 0, len(parts))
	for _, part := range parts {
		v, err := strconv.ParseInt(strings.TrimSpace(part), 10, 64)
		if err != nil {
			return fmt.Errorf("parse bigint array item %q: %w", part, err)
		}
		out = append(out, v)
	}
	*a = out
	return nil
}

type FeatureDefinition struct {
	ID          uint64    `gorm:"primaryKey;autoIncrement" json:"id"`
	FeatureCode string    `gorm:"column:feature_code;type:varchar(160);not null;uniqueIndex" json:"feature_code"`
	DisplayName string    `gorm:"column:display_name;type:varchar(256);not null" json:"display_name"`
	Description string    `gorm:"type:text;not null" json:"description"`
	Kind        string    `gorm:"type:varchar(32);not null" json:"kind"`
	EntityType  string    `gorm:"column:entity_type;type:varchar(32);not null" json:"entity_type"`
	ValueType   string    `gorm:"column:value_type;type:varchar(32);not null" json:"value_type"`
	Unit        string    `gorm:"type:varchar(64);not null" json:"unit"`
	Category    string    `gorm:"type:varchar(64);not null" json:"category"`
	Owner       string    `gorm:"type:varchar(128);not null" json:"owner"`
	Status      string    `gorm:"type:varchar(32);not null" json:"status"`
	Tags        JSONValue `gorm:"type:jsonb;not null" json:"tags"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

func (FeatureDefinition) TableName() string { return "govern.feature_definition" }

type FeatureVersion struct {
	ID               uint64     `gorm:"primaryKey;autoIncrement" json:"id"`
	FeatureID        uint64     `gorm:"column:feature_id;not null;index" json:"feature_id"`
	VersionNumber    int        `gorm:"column:version_number;not null" json:"version_number"`
	Status           string     `gorm:"type:varchar(32);not null" json:"status"`
	Frequency        string     `gorm:"type:varchar(32);not null" json:"frequency"`
	AsOfSemantics    string     `gorm:"column:as_of_semantics;type:varchar(32);not null" json:"as_of_semantics"`
	MissingPolicy    string     `gorm:"column:missing_policy;type:varchar(32);not null" json:"missing_policy"`
	ManifestChecksum string     `gorm:"column:manifest_checksum;type:char(64);not null" json:"manifest_checksum"`
	ManifestSnapshot JSONValue  `gorm:"column:manifest_snapshot;type:jsonb;not null" json:"manifest_snapshot"`
	PublishedAt      *time.Time `gorm:"column:published_at" json:"published_at,omitempty"`
	DeprecatedAt     *time.Time `gorm:"column:deprecated_at" json:"deprecated_at,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

func (FeatureVersion) TableName() string { return "govern.feature_version" }

type FeatureImplementation struct {
	ID                     uint64    `gorm:"primaryKey;autoIncrement" json:"id"`
	FeatureVersionID       uint64    `gorm:"column:feature_version_id;not null;index" json:"feature_version_id"`
	Kind                   string    `gorm:"type:varchar(32);not null" json:"kind"`
	ProducerService        string    `gorm:"column:producer_service;type:varchar(64);not null" json:"producer_service"`
	Backend                string    `gorm:"type:varchar(64);not null" json:"backend"`
	Entrypoint             string    `gorm:"type:varchar(512);not null" json:"entrypoint"`
	ImplementationRevision int       `gorm:"column:implementation_revision;not null" json:"implementation_revision"`
	Config                 JSONValue `gorm:"type:jsonb;not null" json:"config"`
	Checksum               string    `gorm:"type:char(64);not null" json:"checksum"`
	IsCanonical            bool      `gorm:"column:is_canonical;not null" json:"is_canonical"`
	Status                 string    `gorm:"type:varchar(32);not null" json:"status"`
	CreatedAt              time.Time `json:"created_at"`
	UpdatedAt              time.Time `json:"updated_at"`
}

func (FeatureImplementation) TableName() string { return "govern.feature_implementation" }

type FeatureDependency struct {
	ID                          uint64    `gorm:"primaryKey;autoIncrement" json:"id"`
	FeatureVersionID            uint64    `gorm:"column:feature_version_id;not null;index" json:"feature_version_id"`
	DependencyKind              string    `gorm:"column:dependency_kind;type:varchar(32);not null" json:"dependency_kind"`
	DependsOnFeatureVersionID   *uint64   `gorm:"column:depends_on_feature_version_id" json:"depends_on_feature_version_id,omitempty"`
	DataFieldDictionaryID       *uint64   `gorm:"column:data_field_dictionary_id" json:"data_field_dictionary_id,omitempty"`
	DependencyReferenceSnapshot JSONValue `gorm:"column:dependency_ref_snapshot;type:jsonb;not null" json:"dependency_ref_snapshot"`
	Ordinal                     int       `gorm:"not null" json:"ordinal"`
	CreatedAt                   time.Time `json:"created_at"`
}

func (FeatureDependency) TableName() string { return "govern.feature_dependency" }

type FeatureBackfillJob struct {
	BackfillID            string     `gorm:"column:backfill_id;type:uuid;primaryKey" json:"backfill_id"`
	RootFeatureVersionIDs Int64Array `gorm:"column:root_feature_version_ids;type:bigint[];not null" json:"root_feature_version_ids"`
	StartAsOf             time.Time  `gorm:"column:start_as_of;not null" json:"start_as_of"`
	EndAsOf               time.Time  `gorm:"column:end_as_of;not null" json:"end_as_of"`
	Step                  string     `gorm:"type:varchar(32);not null" json:"step"`
	CalendarCode          string     `gorm:"column:calendar_code;type:varchar(64);not null" json:"calendar_code"`
	ExpandedAsOfTimes     JSONValue  `gorm:"column:expanded_as_of_times;type:jsonb;not null" json:"expanded_as_of_times"`
	DataCutoffPolicy      JSONValue  `gorm:"column:data_cutoff_policy;type:jsonb;not null" json:"data_cutoff_policy"`
	SourceProfile         string     `gorm:"column:source_profile;type:varchar(64);not null" json:"source_profile"`
	Market                string     `gorm:"type:varchar(32);not null" json:"market"`
	UniverseRequest       JSONValue  `gorm:"column:universe_request;type:jsonb;not null" json:"universe_request"`
	MaxConcurrency        int        `gorm:"column:max_concurrency;not null" json:"max_concurrency"`
	Status                string     `gorm:"type:varchar(32);not null" json:"status"`
	TotalCount            int        `gorm:"column:total_count;not null" json:"total_count"`
	SucceededCount        int        `gorm:"column:succeeded_count;not null" json:"succeeded_count"`
	FailedCount           int        `gorm:"column:failed_count;not null" json:"failed_count"`
	CreatedAt             time.Time  `json:"created_at"`
	UpdatedAt             time.Time  `json:"updated_at"`
}

func (FeatureBackfillJob) TableName() string { return "govern.feature_backfill_job" }

type FeatureRun struct {
	RunID              string     `gorm:"column:run_id;type:uuid;primaryKey" json:"run_id"`
	RequestFingerprint string     `gorm:"column:request_fingerprint;type:char(64);not null;index" json:"request_fingerprint"`
	ProducerService    string     `gorm:"column:producer_service;type:varchar(64);not null" json:"producer_service"`
	ProducerRunRef     string     `gorm:"column:producer_run_ref;type:varchar(128);not null" json:"producer_run_ref"`
	TriggerType        string     `gorm:"column:trigger_type;type:varchar(32);not null" json:"trigger_type"`
	AsOfTime           time.Time  `gorm:"column:as_of_time;not null" json:"as_of_time"`
	DataCutoffTime     time.Time  `gorm:"column:data_cutoff_time;not null" json:"data_cutoff_time"`
	SourceProfile      string     `gorm:"column:source_profile;type:varchar(64);not null" json:"source_profile"`
	Market             string     `gorm:"type:varchar(32);not null" json:"market"`
	UniverseHash       string     `gorm:"column:universe_hash;type:char(64);not null" json:"universe_hash"`
	RequestPayload     JSONValue  `gorm:"column:request_payload;type:jsonb;not null" json:"request_payload"`
	CodeRevision       string     `gorm:"column:code_revision;type:varchar(128);not null" json:"code_revision"`
	Status             string     `gorm:"type:varchar(32);not null" json:"status"`
	RetryOfRunID       *string    `gorm:"column:retry_of_run_id;type:uuid" json:"retry_of_run_id,omitempty"`
	WorkerID           string     `gorm:"column:worker_id;type:varchar(128);not null" json:"worker_id"`
	HeartbeatAt        *time.Time `gorm:"column:heartbeat_at" json:"heartbeat_at,omitempty"`
	BackfillID         *string    `gorm:"column:backfill_id;type:uuid" json:"backfill_id,omitempty"`
	BackfillSequence   *int       `gorm:"column:backfill_sequence" json:"backfill_sequence,omitempty"`
	BackfillAttempt    *int       `gorm:"column:backfill_attempt" json:"backfill_attempt,omitempty"`
	StartedAt          *time.Time `gorm:"column:started_at" json:"started_at,omitempty"`
	FinishedAt         *time.Time `gorm:"column:finished_at" json:"finished_at,omitempty"`
	ErrorCode          string     `gorm:"column:error_code;type:varchar(64);not null" json:"error_code"`
	ErrorMessage       string     `gorm:"column:error_message;type:text;not null" json:"error_message"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

func (FeatureRun) TableName() string { return "govern.feature_run" }

type FeatureRunItem struct {
	RunID            string     `gorm:"column:run_id;type:uuid;primaryKey" json:"run_id"`
	FeatureVersionID uint64     `gorm:"column:feature_version_id;primaryKey" json:"feature_version_id"`
	Status           string     `gorm:"type:varchar(32);not null" json:"status"`
	InputCount       int64      `gorm:"column:input_count;not null" json:"input_count"`
	OutputCount      int64      `gorm:"column:output_count;not null" json:"output_count"`
	ValidCount       int64      `gorm:"column:valid_count;not null" json:"valid_count"`
	MissingCount     int64      `gorm:"column:missing_count;not null" json:"missing_count"`
	InvalidCount     int64      `gorm:"column:invalid_count;not null" json:"invalid_count"`
	QualitySummary   JSONValue  `gorm:"column:quality_summary;type:jsonb;not null" json:"quality_summary"`
	DurationMS       int64      `gorm:"column:duration_ms;not null" json:"duration_ms"`
	ErrorCode        string     `gorm:"column:error_code;type:varchar(64);not null" json:"error_code"`
	ErrorMessage     string     `gorm:"column:error_message;type:text;not null" json:"error_message"`
	StartedAt        *time.Time `gorm:"column:started_at" json:"started_at,omitempty"`
	FinishedAt       *time.Time `gorm:"column:finished_at" json:"finished_at,omitempty"`
}

func (FeatureRunItem) TableName() string { return "govern.feature_run_item" }

type FeatureRunSubject struct {
	RunID          string `gorm:"column:run_id;type:uuid;primaryKey" json:"run_id"`
	SecurityID     uint64 `gorm:"column:security_id;primaryKey" json:"security_id"`
	SymbolSnapshot string `gorm:"column:symbol_snapshot;type:varchar(32);not null" json:"symbol_snapshot"`
	Exchange       string `gorm:"column:exchange_snapshot;type:varchar(16);not null" json:"exchange_snapshot"`
	AssetType      string `gorm:"column:asset_type_snapshot;type:varchar(32);not null" json:"asset_type_snapshot"`
	IncludedReason string `gorm:"column:included_reason;type:varchar(128);not null" json:"included_reason"`
}

func (FeatureRunSubject) TableName() string { return "govern.feature_run_subject" }

type FeatureNumericValue struct {
	RunID                string     `gorm:"column:run_id;type:uuid;primaryKey" json:"run_id"`
	FeatureVersionID     uint64     `gorm:"column:feature_version_id;primaryKey" json:"feature_version_id"`
	SecurityID           uint64     `gorm:"column:security_id;primaryKey" json:"security_id"`
	ObservedAt           time.Time  `gorm:"column:observed_at;primaryKey" json:"observed_at"`
	Value                *float64   `gorm:"column:value" json:"value"`
	ValueStatus          string     `gorm:"column:value_status;type:varchar(16);not null" json:"value_status"`
	QualityFlags         JSONValue  `gorm:"column:quality_flags;type:jsonb;not null" json:"quality_flags"`
	SourceMaxAvailableAt *time.Time `gorm:"column:source_max_available_at" json:"source_max_available_at,omitempty"`
	ComputedAt           time.Time  `gorm:"column:computed_at;not null" json:"computed_at"`
}

func (FeatureNumericValue) TableName() string { return "dwd.feature_value_numeric" }

// Registry API contracts.
type FeatureDefinitionSpec struct {
	Code        string   `json:"code"`
	DisplayName string   `json:"display_name"`
	Description string   `json:"description"`
	Kind        string   `json:"kind"`
	EntityType  string   `json:"entity_type"`
	ValueType   string   `json:"value_type"`
	Unit        string   `json:"unit"`
	Category    string   `json:"category"`
	Owner       string   `json:"owner"`
	Tags        []string `json:"tags"`
}

type FeatureVersionSpec struct {
	Number           int    `json:"number"`
	Status           string `json:"status"`
	Frequency        string `json:"frequency"`
	AsOfSemantics    string `json:"as_of_semantics"`
	MissingPolicy    string `json:"missing_policy"`
	ManifestChecksum string `json:"manifest_checksum"`
}

type FeatureImplementationSpec struct {
	Kind                   string         `json:"kind"`
	ProducerService        string         `json:"producer_service"`
	Backend                string         `json:"backend"`
	Entrypoint             string         `json:"entrypoint"`
	ImplementationRevision int            `json:"implementation_revision"`
	Config                 map[string]any `json:"config"`
	Checksum               string         `json:"checksum"`
	Status                 string         `json:"status"`
}

type FeatureDependencySpec struct {
	Kind            string `json:"kind"`
	FeatureCode     string `json:"feature_code,omitempty"`
	FeatureVersion  int    `json:"feature_version,omitempty"`
	Source          string `json:"source,omitempty"`
	Dataset         string `json:"dataset,omitempty"`
	DataType        string `json:"data_type,omitempty"`
	RawField        string `json:"raw_field,omitempty"`
	ContractVersion string `json:"contract_version,omitempty"`
}

type FeatureManifest struct {
	Feature        FeatureDefinitionSpec     `json:"feature"`
	Version        FeatureVersionSpec        `json:"version"`
	Implementation FeatureImplementationSpec `json:"implementation"`
	Dependencies   []FeatureDependencySpec   `json:"dependencies"`
}

type FeatureRegistrySyncRequest struct {
	Manifests []FeatureManifest `json:"manifests"`
}

type FeatureSyncRejection struct {
	Feature string `json:"feature"`
	Code    string `json:"code"`
	Error   string `json:"error"`
}

type FeatureRegistrySyncResponse struct {
	Created       []string               `json:"created"`
	UpdatedDrafts []string               `json:"updated_drafts"`
	Unchanged     []string               `json:"unchanged"`
	Rejected      []FeatureSyncRejection `json:"rejected"`
	GraphValid    bool                   `json:"graph_valid"`
}

type FeatureDefinitionDetail struct {
	Definition FeatureDefinition       `json:"definition"`
	Versions   []FeatureVersionSummary `json:"versions"`
}

type FeatureVersionSummary struct {
	Version         FeatureVersion          `json:"version"`
	Implementations []FeatureImplementation `json:"implementations"`
	Dependencies    []FeatureDependency     `json:"dependencies"`
}

type FeatureLineage struct {
	FeatureCode string                  `json:"feature_code"`
	Versions    []FeatureLineageVersion `json:"versions"`
}

type FeatureLineageVersion struct {
	FeatureVersionID   uint64                    `json:"feature_version_id"`
	VersionNumber      int                       `json:"version_number"`
	Upstream           []FeatureDependency       `json:"upstream"`
	Downstream         []FeatureDependency       `json:"downstream"`
	UpstreamFeatures   []FeatureLineageReference `json:"upstream_features"`
	DownstreamFeatures []FeatureLineageReference `json:"downstream_features"`
	UpstreamDataFields []FeatureLineageDataField `json:"upstream_data_fields"`
}

type FeatureLineageReference struct {
	FeatureVersionID uint64 `json:"feature_version_id"`
	FeatureCode      string `json:"feature_code"`
	VersionNumber    int    `json:"version_number"`
	Status           string `json:"status"`
}

type FeatureLineageDataField struct {
	DataFieldDictionaryID uint64 `json:"data_field_dictionary_id"`
	Source                string `json:"source"`
	Dataset               string `json:"dataset"`
	DataType              string `json:"data_type"`
	RawField              string `json:"raw_field"`
	ContractVersion       string `json:"contract_version"`
	StorageLocation       string `json:"storage_location"`
	Deprecated            bool   `json:"deprecated"`
}

type FeatureAvailability struct {
	FeatureCode           string                         `json:"feature_code"`
	SourceProfile         string                         `json:"source_profile"`
	LatestPublishedID     *uint64                        `json:"latest_published_version_id,omitempty"`
	LatestSucceededRun    *FeatureRun                    `json:"latest_succeeded_run,omitempty"`
	Status                string                         `json:"status"`
	DefinitionStatus      string                         `json:"definition_status"`
	VersionStatus         string                         `json:"version_status"`
	DependencyStatus      string                         `json:"dependency_status"`
	DataStatus            string                         `json:"data_status"`
	ImplementationStatus  string                         `json:"implementation_status"`
	MaterializationStatus string                         `json:"materialization_status"`
	ExecutionReadiness    string                         `json:"execution_readiness"`
	Reasons               []string                       `json:"reasons"`
	DataFields            []FeatureDataFieldAvailability `json:"data_fields"`
}

type FeatureDataFieldAvailability struct {
	FeatureLineageDataField
	Status      string     `json:"status"`
	SampleCount int64      `json:"sample_count"`
	LastSeenAt  *time.Time `json:"last_seen_at,omitempty"`
}

// Run/value API contracts.
type FeatureRunCreateRequest struct {
	RunID                  string         `json:"run_id,omitempty"`
	RequestFingerprint     string         `json:"request_fingerprint"`
	ProducerService        string         `json:"producer_service"`
	ProducerRunRef         string         `json:"producer_run_ref,omitempty"`
	TriggerType            string         `json:"trigger_type"`
	AsOfTime               time.Time      `json:"as_of_time"`
	DataCutoffTime         time.Time      `json:"data_cutoff_time"`
	SourceProfile          string         `json:"source_profile"`
	Market                 string         `json:"market"`
	UniverseHash           string         `json:"universe_hash"`
	CodeRevision           string         `json:"code_revision"`
	RootFeatureVersionIDs  []uint64       `json:"root_feature_version_ids"`
	DependencyPlanChecksum string         `json:"dependency_plan_checksum,omitempty"`
	Parameters             map[string]any `json:"parameters,omitempty"`
	RetryOfRunID           *string        `json:"retry_of_run_id,omitempty"`
	Force                  bool           `json:"force,omitempty"`
}

type FeatureRunCreateResponse struct {
	Accepted           bool   `json:"accepted"`
	Reused             bool   `json:"reused"`
	RunID              string `json:"run_id"`
	Status             string `json:"status"`
	RequestFingerprint string `json:"request_fingerprint"`
}

type FeatureSubjectsBatchRequest struct {
	SecurityIDs    []uint64 `json:"security_ids"`
	IncludedReason string   `json:"included_reason,omitempty"`
}

type FeatureItemsBatchRequest struct {
	FeatureVersionIDs []uint64 `json:"feature_version_ids"`
}

type FeatureStateUpdateRequest struct {
	ExpectedStatus string     `json:"expected_status"`
	NewStatus      string     `json:"new_status"`
	WorkerID       string     `json:"worker_id,omitempty"`
	HeartbeatAt    *time.Time `json:"heartbeat_at,omitempty"`
	ErrorCode      string     `json:"error_code,omitempty"`
	ErrorMessage   string     `json:"error_message,omitempty"`
}

type FeatureRunItemUpdateRequest struct {
	ExpectedStatus string         `json:"expected_status"`
	NewStatus      string         `json:"new_status"`
	InputCount     int64          `json:"input_count"`
	OutputCount    int64          `json:"output_count"`
	ValidCount     int64          `json:"valid_count"`
	MissingCount   int64          `json:"missing_count"`
	InvalidCount   int64          `json:"invalid_count"`
	DurationMS     int64          `json:"duration_ms"`
	QualitySummary map[string]any `json:"quality_summary,omitempty"`
	ErrorCode      string         `json:"error_code,omitempty"`
	ErrorMessage   string         `json:"error_message,omitempty"`
}

type FeatureStaleRunReconcileRequest struct {
	StaleBefore     time.Time `json:"stale_before"`
	ProducerService string    `json:"producer_service"`
}

type FeatureStaleRunReconcileResponse struct {
	StaleBefore  time.Time `json:"stale_before"`
	AbortedCount int       `json:"aborted_count"`
	RunIDs       []string  `json:"run_ids"`
}

type FeatureNumericBatchRequest struct {
	FeatureVersionID uint64                `json:"feature_version_id"`
	ObservedAt       time.Time             `json:"observed_at"`
	Values           []FeatureNumericInput `json:"values"`
}

type FeatureNumericInput struct {
	SecurityID           uint64         `json:"security_id"`
	Value                *float64       `json:"value"`
	ValueStatus          string         `json:"value_status"`
	QualityFlags         map[string]any `json:"quality_flags,omitempty"`
	SourceMaxAvailableAt *time.Time     `json:"source_max_available_at,omitempty"`
}

type FeatureRunDetail struct {
	Run      FeatureRun          `json:"run"`
	Items    []FeatureRunItem    `json:"items"`
	Subjects []FeatureRunSubject `json:"subjects,omitempty"`
}

type FeatureRunFilters struct {
	Status           string
	ProducerService  string
	FeatureVersionID uint64
	BackfillID       string
}

type FeatureValueQuery struct {
	FeatureCode      string
	VersionNumber    int
	FeatureVersionID uint64
	SecurityIDs      []uint64
	ObservedFrom     *time.Time
	ObservedTo       *time.Time
	RunID            string
	Latest           bool
	Limit            int
	Offset           int
}

type FeatureBackfillCreateRequest struct {
	RootFeatureVersionIDs  []uint64       `json:"root_feature_version_ids"`
	StartAsOf              time.Time      `json:"start_as_of"`
	EndAsOf                time.Time      `json:"end_as_of"`
	Step                   string         `json:"step"`
	ExplicitAsOfTimes      []time.Time    `json:"explicit_as_of_times,omitempty"`
	CalendarCode           string         `json:"calendar_code,omitempty"`
	DataCutoffPolicy       map[string]any `json:"data_cutoff_policy"`
	SourceProfile          string         `json:"source_profile"`
	Market                 string         `json:"market"`
	UniverseRequest        map[string]any `json:"universe_request"`
	UniverseHash           string         `json:"universe_hash"`
	MaxConcurrency         int            `json:"max_concurrency"`
	ProducerService        string         `json:"producer_service"`
	CodeRevision           string         `json:"code_revision"`
	DependencyPlanChecksum string         `json:"dependency_plan_checksum,omitempty"`
}
