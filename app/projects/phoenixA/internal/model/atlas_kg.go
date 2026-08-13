package model

import (
	"encoding/json"
	"time"
)

type AtlasExtractionRun struct {
	ID               string          `gorm:"type:uuid;primaryKey" json:"id"`
	SourceDocumentID string          `gorm:"type:varchar(160);not null;index" json:"source_document_id"`
	SourceReportType string          `gorm:"type:varchar(32);not null;index" json:"source_report_type"`
	Status           string          `gorm:"type:varchar(32);not null;index" json:"status"`
	Payload          json.RawMessage `gorm:"type:jsonb;not null" json:"payload"`
	Result           json.RawMessage `gorm:"type:jsonb" json:"result,omitempty"`
	CreatedAt        time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt        time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasExtractionRun) TableName() string { return "atlas_kg.extraction_run" }

type AtlasGovernanceRecord struct {
	ID        string          `gorm:"type:uuid;primaryKey" json:"id"`
	Kind      string          `gorm:"type:varchar(32);not null;index" json:"kind"`
	Version   string          `gorm:"type:varchar(80);not null;default:'';index" json:"version"`
	Status    string          `gorm:"type:varchar(32);not null;index" json:"status"`
	Payload   json.RawMessage `gorm:"type:jsonb;not null" json:"payload"`
	CreatedAt time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasGovernanceRecord) TableName() string { return "atlas_kg.governance_record" }

type AtlasKnowledgeEntity struct {
	ID              string          `gorm:"type:uuid;primaryKey" json:"id"`
	CanonicalName   string          `gorm:"type:varchar(512);not null;index" json:"canonical_name"`
	NormalizedName  string          `gorm:"type:varchar(512);not null;index" json:"normalized_name"`
	EntityType      string          `gorm:"type:varchar(32);not null;index" json:"entity_type"`
	CountryCode     string          `gorm:"type:varchar(16);not null;default:''" json:"country_code"`
	ResolutionState string          `gorm:"type:varchar(32);not null;index" json:"resolution_state"`
	Attributes      json.RawMessage `gorm:"type:jsonb;not null" json:"attributes"`
	CreatedAt       time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasKnowledgeEntity) TableName() string { return "atlas_kg.knowledge_entity" }

type AtlasEntityAlias struct {
	ID              int64     `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	EntityID        string    `gorm:"type:uuid;not null;uniqueIndex:uk_atlas_entity_alias" json:"entity_id"`
	Alias           string    `gorm:"type:varchar(512);not null" json:"alias"`
	NormalizedAlias string    `gorm:"type:varchar(512);not null;uniqueIndex:uk_atlas_entity_alias" json:"normalized_alias"`
	Language        string    `gorm:"type:varchar(16);not null;default:''" json:"language"`
	Source          string    `gorm:"type:varchar(64);not null;default:''" json:"source"`
	CreatedAt       time.Time `gorm:"autoCreateTime" json:"created_at"`
}

func (AtlasEntityAlias) TableName() string { return "atlas_kg.entity_alias" }

type AtlasSecurityEntityLink struct {
	EntityID         string    `gorm:"type:uuid;primaryKey" json:"entity_id"`
	SecurityID       int64     `gorm:"not null;uniqueIndex" json:"security_id"`
	Confidence       float64   `gorm:"type:numeric(5,4);not null" json:"confidence"`
	ResolutionMethod string    `gorm:"type:varchar(40);not null" json:"resolution_method"`
	CreatedAt        time.Time `gorm:"autoCreateTime" json:"created_at"`
}

func (AtlasSecurityEntityLink) TableName() string { return "atlas_kg.security_entity_link" }

type AtlasClaim struct {
	ID                 string          `gorm:"type:uuid;primaryKey" json:"id"`
	ClaimType          string          `gorm:"type:varchar(32);not null;index" json:"claim_type"`
	SourceDocumentID   string          `gorm:"type:varchar(160);not null;index" json:"source_document_id"`
	SubjectEntityID    *string         `gorm:"type:uuid;index" json:"subject_entity_id,omitempty"`
	ObjectEntityID     *string         `gorm:"type:uuid;index" json:"object_entity_id,omitempty"`
	CanonicalPredicate string          `gorm:"type:varchar(128);not null;default:'';index" json:"canonical_predicate"`
	AssertionType      string          `gorm:"type:varchar(40);not null;index" json:"assertion_type"`
	Status             string          `gorm:"type:varchar(24);not null;index" json:"status"`
	Payload            json.RawMessage `gorm:"type:jsonb;not null" json:"payload"`
	CreatedAt          time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt          time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasClaim) TableName() string { return "atlas_kg.claim" }

// AtlasSampleRun 记录一次完整采样任务的状态与进度。
type AtlasSampleRun struct {
	ID                 string          `gorm:"type:uuid;primaryKey" json:"id"`
	RequestPayload     json.RawMessage `gorm:"type:jsonb;not null;default:'{}'::jsonb" json:"request_payload"`
	Status             string          `gorm:"type:varchar(50);not null;default:PENDING;index" json:"status"`
	CronjobRunID       *int64          `gorm:"index" json:"cronjob_run_id,omitempty"`
	SampledDocumentIDs StringArray     `gorm:"type:text[];not null;default:'{}'" json:"sampled_document_ids"`
	Current            int             `gorm:"not null;default:0" json:"current"`
	Total              int             `gorm:"not null;default:0" json:"total"`
	ProgressMessage    *string         `json:"progress_message,omitempty"`
	StartedAt          *time.Time      `json:"started_at,omitempty"`
	CompletedAt        *time.Time      `json:"completed_at,omitempty"`
	ErrorCode          *string         `json:"error_code,omitempty"`
	ErrorMessage       *string         `json:"error_message,omitempty"`
	CreatedAt          time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt          time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasSampleRun) TableName() string { return "atlas_kg.sample_run" }

// AtlasSampleCategoryResult 每类采样的聚合 JSON 产出,含人审 field_summary。
type AtlasSampleCategoryResult struct {
	ID            string          `gorm:"type:uuid;primaryKey" json:"id"`
	SampleRunID   string          `gorm:"type:uuid;not null;uniqueIndex:uidx_sample_category,priority:1;index:idx_sample_category_run" json:"sample_run_id"`
	ReportType    string          `gorm:"not null;uniqueIndex:uidx_sample_category,priority:2" json:"report_type"`
	DocumentCount int             `gorm:"not null;default:0" json:"document_count"`
	RawResults    json.RawMessage `gorm:"type:jsonb;not null;default:'[]'::jsonb" json:"raw_results"`
	FieldSummary  json.RawMessage `gorm:"type:jsonb" json:"field_summary,omitempty"`
	GeneratedAt   *time.Time      `json:"generated_at,omitempty"`
	CreatedAt     time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasSampleCategoryResult) TableName() string { return "atlas_kg.sample_category_result" }

// AtlasSampleDocumentResult 单个采样文档的处理明细,关联 extraction_run。
type AtlasSampleDocumentResult struct {
	ID              string     `gorm:"type:uuid;primaryKey" json:"id"`
	SampleRunID     string     `gorm:"type:uuid;not null;index:idx_sample_doc_run" json:"sample_run_id"`
	DocumentID      string     `gorm:"not null;index:idx_sample_doc_document" json:"document_id"`
	ReportType      string     `gorm:"not null" json:"report_type"`
	ExtractionRunID string     `gorm:"type:uuid;not null" json:"extraction_run_id"`
	Status          string     `gorm:"type:varchar(50);not null;default:PENDING" json:"status"`
	StartedAt       *time.Time `json:"started_at,omitempty"`
	CompletedAt     *time.Time `json:"completed_at,omitempty"`
	DurationMs      *int       `gorm:"check:duration_ms >= 0" json:"duration_ms,omitempty"`
	ErrorCode       *string    `json:"error_code,omitempty"`
	ErrorMessage    *string    `json:"error_message,omitempty"`
	CreatedAt       time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time  `gorm:"autoUpdateTime" json:"updated_at"`
}

func (AtlasSampleDocumentResult) TableName() string { return "atlas_kg.sample_document_result" }
