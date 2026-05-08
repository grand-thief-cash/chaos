package model

import (
	"database/sql/driver"
	"encoding/json"
	"fmt"
	"time"
)

// StringArray is a custom type for PostgreSQL TEXT[] arrays compatible with GORM.
type StringArray []string

func (a StringArray) Value() (driver.Value, error) {
	if a == nil {
		return "{}", nil
	}
	// PostgreSQL array literal: {val1,val2,...}
	result := "{"
	for i, v := range a {
		if i > 0 {
			result += ","
		}
		result += fmt.Sprintf("%q", v)
	}
	result += "}"
	return result, nil
}

func (a *StringArray) Scan(src interface{}) error {
	if src == nil {
		*a = StringArray{}
		return nil
	}
	switch v := src.(type) {
	case []byte:
		return a.parseArray(string(v))
	case string:
		return a.parseArray(v)
	default:
		return fmt.Errorf("unsupported type for StringArray: %T", src)
	}
}

func (a *StringArray) parseArray(s string) error {
	if s == "{}" || s == "" {
		*a = StringArray{}
		return nil
	}
	// Simple parser for PostgreSQL text array format {val1,val2,...}
	s = s[1 : len(s)-1] // remove { }
	var items []string
	current := ""
	inQuote := false
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == '"' {
			inQuote = !inQuote
		} else if c == ',' && !inQuote {
			items = append(items, current)
			current = ""
		} else {
			current += string(c)
		}
	}
	if current != "" {
		items = append(items, current)
	}
	*a = items
	return nil
}

// JSONB is a helper type for PostgreSQL JSONB columns.
type JSONB map[string]interface{}

func (j JSONB) Value() (driver.Value, error) {
	if j == nil {
		return "{}", nil
	}
	b, err := json.Marshal(j)
	if err != nil {
		return nil, err
	}
	return string(b), nil
}

func (j *JSONB) Scan(src interface{}) error {
	if src == nil {
		*j = JSONB{}
		return nil
	}
	var data []byte
	switch v := src.(type) {
	case []byte:
		data = v
	case string:
		data = []byte(v)
	default:
		return fmt.Errorf("unsupported type for JSONB: %T", src)
	}
	return json.Unmarshal(data, j)
}

// ── KG Domain Models ──────────────────────────────────────────────────────

// KgDocument represents a document in the knowledge graph pipeline.
type KgDocument struct {
	ID          int64      `gorm:"primaryKey;autoIncrement" json:"id"`
	DocID       string     `gorm:"column:doc_id;type:varchar(64);uniqueIndex;not null" json:"doc_id"`
	Title       string     `gorm:"type:varchar(512)" json:"title"`
	DocType     string     `gorm:"column:doc_type;type:varchar(32);not null" json:"doc_type"`
	SourceType  string     `gorm:"column:source_type;type:varchar(16);not null;default:'event'" json:"source_type"`
	Company     string     `gorm:"type:varchar(128)" json:"company"`
	PublishTime *time.Time `gorm:"column:publish_time" json:"publish_time,omitempty"`
	FilePath    string     `gorm:"column:file_path;type:varchar(1024)" json:"file_path"`
	ContentHash string     `gorm:"column:content_hash;type:varchar(64)" json:"content_hash"`
	Processed   bool       `gorm:"default:false" json:"processed"`
	CreatedAt   time.Time  `gorm:"autoCreateTime" json:"created_at"`
}

func (KgDocument) TableName() string { return "kg.documents" }

// KgDocumentFilters for querying documents.
type KgDocumentFilters struct {
	DocType     string
	SourceType  string
	Company     string
	Processed   *bool
	ContentHash string
}

// KgExtraction represents an LLM extraction result.
type KgExtraction struct {
	ID            int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	DocID         string    `gorm:"column:doc_id;type:varchar(64);not null" json:"doc_id"`
	ChunkIndex    int       `gorm:"column:chunk_index;not null" json:"chunk_index"`
	PromptVersion string    `gorm:"column:prompt_version;type:varchar(16);not null" json:"prompt_version"`
	LLMModel      string    `gorm:"column:llm_model;type:varchar(64)" json:"llm_model"`
	GraphJSON     JSONB     `gorm:"column:graph_json;type:jsonb;not null" json:"graph_json"`
	InputTokens   int       `gorm:"column:input_tokens" json:"input_tokens"`
	OutputTokens  int       `gorm:"column:output_tokens" json:"output_tokens"`
	CostUSD       float64   `gorm:"column:cost_usd;type:decimal(10,6)" json:"cost_usd"`
	QualityScore  *float64  `gorm:"column:quality_score" json:"quality_score,omitempty"`
	Status        string    `gorm:"type:varchar(16);default:'completed'" json:"status"`
	CreatedAt     time.Time `gorm:"autoCreateTime" json:"created_at"`
}

func (KgExtraction) TableName() string { return "kg.extractions" }

// KgExtractionFilters for querying extractions.
type KgExtractionFilters struct {
	DocID         string
	PromptVersion string
	Status        string
}

// KgEvent represents a normalized/deduplicated event.
type KgEvent struct {
	ID               int64       `gorm:"primaryKey;autoIncrement" json:"id"`
	EventFingerprint string      `gorm:"column:event_fingerprint;type:varchar(64);uniqueIndex;not null" json:"event_fingerprint"`
	EntityName       string      `gorm:"column:entity_name;type:varchar(256);not null" json:"entity_name"`
	EventType        string      `gorm:"column:event_type;type:varchar(32);not null" json:"event_type"`
	Direction        string      `gorm:"type:varchar(16)" json:"direction"`
	TimeBucket       string      `gorm:"column:time_bucket;type:varchar(16);not null" json:"time_bucket"`
	Description      string      `gorm:"type:text" json:"description"`
	Severity         string      `gorm:"type:varchar(8);default:'medium'" json:"severity"`
	SourceDocIDs     StringArray `gorm:"column:source_doc_ids;type:text[]" json:"source_doc_ids"`
	SourceCount      int         `gorm:"column:source_count;default:1" json:"source_count"`
	FirstSeenAt      time.Time   `gorm:"column:first_seen_at;autoCreateTime" json:"first_seen_at"`
	LastSeenAt       time.Time   `gorm:"column:last_seen_at;autoCreateTime" json:"last_seen_at"`
	ImpactTriggered  bool        `gorm:"column:impact_triggered;default:false" json:"impact_triggered"`
	CreatedAt        time.Time   `gorm:"autoCreateTime" json:"created_at"`
}

func (KgEvent) TableName() string { return "kg.events" }

// KgEventFilters for querying events.
type KgEventFilters struct {
	Fingerprint string
	EventType   string
	EntityName  string
	TimeBucket  string
	StartTime   string // ISO date for first_seen_at >=
	EndTime     string // ISO date for first_seen_at <=
}

// KgGraphIngestion records a graph write operation.
type KgGraphIngestion struct {
	ID           int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	ExtractionID int64     `gorm:"column:extraction_id" json:"extraction_id"`
	NodesCreated int       `gorm:"column:nodes_created;default:0" json:"nodes_created"`
	EdgesCreated int       `gorm:"column:edges_created;default:0" json:"edges_created"`
	NodesMerged  int       `gorm:"column:nodes_merged;default:0" json:"nodes_merged"`
	IngestedAt   time.Time `gorm:"column:ingested_at;autoCreateTime" json:"ingested_at"`
}

func (KgGraphIngestion) TableName() string { return "kg.graph_ingestions" }

// KgDailyRun records a daily pipeline execution.
type KgDailyRun struct {
	ID               int64      `gorm:"primaryKey;autoIncrement" json:"id"`
	RunDate          string     `gorm:"column:run_date;type:date;not null" json:"run_date"`
	DocsFetched      int        `gorm:"column:docs_fetched;default:0" json:"docs_fetched"`
	DocsGraphBuild   int        `gorm:"column:docs_graph_building;default:0" json:"docs_graph_building"`
	DocsEvent        int        `gorm:"column:docs_event;default:0" json:"docs_event"`
	EventsNew        int        `gorm:"column:events_new;default:0" json:"events_new"`
	EventsDeduped    int        `gorm:"column:events_deduped;default:0" json:"events_deduped"`
	ExtractionsOK    int        `gorm:"column:extractions_ok;default:0" json:"extractions_ok"`
	ExtractionsFail  int        `gorm:"column:extractions_fail;default:0" json:"extractions_fail"`
	ImpactsGenerated int        `gorm:"column:impacts_generated;default:0" json:"impacts_generated"`
	TotalCostUSD     float64    `gorm:"column:total_cost_usd;type:decimal(10,4)" json:"total_cost_usd"`
	Status           string     `gorm:"type:varchar(16)" json:"status"`
	StartedAt        *time.Time `gorm:"column:started_at" json:"started_at,omitempty"`
	CompletedAt      *time.Time `gorm:"column:completed_at" json:"completed_at,omitempty"`
}

func (KgDailyRun) TableName() string { return "kg.daily_runs" }

// KgDailyRunFilters for querying daily runs.
type KgDailyRunFilters struct {
	StartDate string
	EndDate   string
	Status    string
}

// KgImpactLog stores impact analysis results.
type KgImpactLog struct {
	ID          int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	EventID     *int64    `gorm:"column:event_id" json:"event_id,omitempty"`
	EventName   string    `gorm:"column:event_name;type:varchar(512)" json:"event_name"`
	EventTime   string    `gorm:"column:event_time;type:varchar(32)" json:"event_time"`
	SourceDocID string    `gorm:"column:source_doc_id;type:varchar(64)" json:"source_doc_id"`
	ImpactJSON  JSONB     `gorm:"column:impact_json;type:jsonb;not null" json:"impact_json"`
	CreatedAt   time.Time `gorm:"autoCreateTime" json:"created_at"`
}

func (KgImpactLog) TableName() string { return "kg.impact_logs" }

// KgImpactLogFilters for querying impact logs.
type KgImpactLogFilters struct {
	EventID   *int64
	EventName string
	StartTime string
	EndTime   string
}
