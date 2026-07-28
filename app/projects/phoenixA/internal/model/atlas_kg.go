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
