package model

import "time"

// ─── Data Catalog Models ───

// CatalogOverview is the top-level summary returned by GET /api/v2/catalog/overview.
type CatalogOverview struct {
	GeneratedAt     time.Time              `json:"generated_at"`
	Cached          bool                   `json:"cached"`
	CacheTTLSeconds int                    `json:"cache_ttl_seconds"`
	Summary         CatalogSummary         `json:"summary"`
	StorageTiers    map[string]TierSummary `json:"storage_tiers"`
	Domains         []DomainCatalogSummary `json:"domains"`
}

// CatalogSummary holds aggregate statistics.
type CatalogSummary struct {
	TotalTables         int    `json:"total_tables"`
	TotalRows           int64  `json:"total_rows"`
	TotalDiskSize       string `json:"total_disk_size"`
	TotalDiskSizeBytes  int64  `json:"total_disk_size_bytes"`
	TotalIndexSize      string `json:"total_index_size"`
	TotalIndexSizeBytes int64  `json:"total_index_size_bytes"`
}

// TierSummary holds per-tablespace statistics.
type TierSummary struct {
	Tablespace    string `json:"tablespace"`
	DiskSize      string `json:"disk_size"`
	DiskSizeBytes int64  `json:"disk_size_bytes"`
	TableCount    int    `json:"table_count"`
}

// DomainCatalogSummary holds per-domain statistics.
type DomainCatalogSummary struct {
	Domain             string `json:"domain"`
	Description        string `json:"description"`
	TableCount         int    `json:"table_count"`
	TotalRows          int64  `json:"total_rows"`
	TotalDiskSize      string `json:"total_disk_size"`
	TotalDiskSizeBytes int64  `json:"total_disk_size_bytes"`
}

// TableCatalogEntry describes a single table in the catalog.
type TableCatalogEntry struct {
	Schema         string     `json:"schema"`
	TableName      string     `json:"table_name"`
	Domain         string     `json:"domain"`
	Description    string     `json:"description"`
	RowCount       int64      `json:"row_count"`
	DiskSize       string     `json:"disk_size"`
	DiskSizeBytes  int64      `json:"disk_size_bytes"`
	IndexSize      string     `json:"index_size"`
	IndexSizeBytes int64      `json:"index_size_bytes"`
	Tablespace     string     `json:"tablespace"`
	StorageTier    string     `json:"storage_tier"`
	IsHypertable   bool       `json:"is_hypertable"`
	TimeRange      *TimeRange `json:"time_range,omitempty"`
	LastModified   *time.Time `json:"last_modified,omitempty"`
	ColumnCount    int        `json:"column_count"`
	HasJSONB       bool       `json:"has_jsonb"`
}

// TimeRange describes the temporal extent of data.
type TimeRange struct {
	Column string `json:"column"`
	Min    string `json:"min"`
	Max    string `json:"max"`
}

// ─── Business-Level Data Visibility ───

// ApiEndpointRef describes a REST API endpoint.
type ApiEndpointRef struct {
	Method      string `json:"method"`
	Path        string `json:"path"`
	Description string `json:"description"`
}

// ExampleCall shows how to query a business domain's data.
type ExampleCall struct {
	Title string `json:"title"`
	URL   string `json:"url"`
}

// CrossRef describes a relationship between tables.
type CrossRef struct {
	ToTable     string `json:"to_table"`
	JoinKey     string `json:"join_key"`
	Description string `json:"description"`
}

// BusinessDomainSummary gives domain context for a table.
type BusinessDomainSummary struct {
	Domain         string   `json:"domain"`
	Label          string   `json:"label"`
	Description    string   `json:"description"`
	TablesInDomain []string `json:"tables_in_domain"`
}

// BusinessOverview is the response for GET /api/v2/catalog/business-overview.
type BusinessOverview struct {
	Domains []BusinessDomain `json:"domains"`
}

// BusinessDomain groups tables by business function with API and cross-ref info.
type BusinessDomain struct {
	Domain       string           `json:"domain"`
	Label        string           `json:"label"`
	Description  string           `json:"description"`
	TableCount   int              `json:"table_count"`
	TotalRows    int64            `json:"total_rows"`
	Tables       []string         `json:"tables"`
	ApiEndpoints []ApiEndpointRef `json:"api_endpoints,omitempty"`
	ExampleCalls []ExampleCall    `json:"example_calls,omitempty"`
	CrossRefs    []CrossRef       `json:"cross_refs,omitempty"`
}

// TableDetail extends TableCatalogEntry with column/index/lineage/business info.
type TableDetail struct {
	TableCatalogEntry
	Columns        []ColumnMeta           `json:"columns"`
	Indexes        []IndexMeta            `json:"indexes"`
	DataLineage    *DataLineage           `json:"data_lineage,omitempty"`
	ApiEndpoints   []ApiEndpointRef       `json:"api_endpoints,omitempty"`
	ExampleCalls   []ExampleCall          `json:"example_calls,omitempty"`
	RelatedTables  []CrossRef             `json:"related_tables,omitempty"`
	BusinessDomain *BusinessDomainSummary `json:"business_domain,omitempty"`
}

// ColumnMeta describes a single table column.
type ColumnMeta struct {
	Name         string `json:"name"`
	Type         string `json:"type"`
	Nullable     bool   `json:"nullable"`
	Description  string `json:"description,omitempty"`
	IsPrimaryKey bool   `json:"is_primary_key,omitempty"`
	JSONBKeys    any    `json:"jsonb_keys,omitempty"`
}

// IndexMeta describes a table index.
type IndexMeta struct {
	Name     string   `json:"name"`
	Columns  []string `json:"columns"`
	IsUnique bool     `json:"is_unique"`
	Type     string   `json:"type,omitempty"`
}

// DataLineage describes data origin and refresh info.
type DataLineage struct {
	SourceSystem    string `json:"source_system"`
	IngestionMethod string `json:"ingestion_method"`
	RefreshSchedule string `json:"refresh_schedule"`
	APIEndpoint     string `json:"api_endpoint,omitempty"`
}

// StorageInfo holds tablespace-level storage info.
type StorageInfo struct {
	Tablespaces []TablespaceInfo `json:"tablespaces"`
}

// TablespaceInfo describes a single tablespace.
type TablespaceInfo struct {
	Name           string   `json:"name"`
	Location       string   `json:"location"`
	Tier           string   `json:"tier"`
	Hardware       string   `json:"hardware"`
	TotalSize      string   `json:"total_size"`
	TotalSizeBytes int64    `json:"total_size_bytes"`
	TableCount     int      `json:"table_count"`
	Tables         []string `json:"tables"`
}

// ─── Neo4j Graph Catalog ───

// GraphCatalogOverview describes the Neo4j graph database contents.
type GraphCatalogOverview struct {
	Available  bool               `json:"available"`
	NodeCounts map[string]int     `json:"node_counts,omitempty"`
	TotalNodes int                `json:"total_nodes"`
	TotalEdges int                `json:"total_edges"`
	Labels     []GraphLabelInfo   `json:"labels,omitempty"`
	RelTypes   []GraphRelTypeInfo `json:"rel_types,omitempty"`
}

// GraphLabelInfo describes a node label in the graph.
type GraphLabelInfo struct {
	Label       string `json:"label"`
	Count       int    `json:"count"`
	Description string `json:"description,omitempty"`
}

// GraphRelTypeInfo describes a relationship type in the graph.
type GraphRelTypeInfo struct {
	Type        string `json:"type"`
	Count       int    `json:"count"`
	Description string `json:"description,omitempty"`
}

// ─── Data Dictionary (comprehensive metadata) ───

// DataDictionary is a machine-readable description of all available data.
// Suitable for UI display and LLM function calling.
type DataDictionary struct {
	GeneratedAt time.Time              `json:"generated_at"`
	Tables      []TableDictionaryEntry `json:"tables"`
}

// TableDictionaryEntry describes a single table with full metadata.
type TableDictionaryEntry struct {
	Schema        string             `json:"schema"`
	TableName     string             `json:"table_name"`
	Domain        string             `json:"domain"`
	Description   string             `json:"description"`
	RowCount      int64              `json:"row_count"`
	Columns       []ColumnDictionary `json:"columns"`
	TimeRange     *TimeRange         `json:"time_range,omitempty"`
	Indexes       []IndexMeta        `json:"indexes"`
	StorageTier   string             `json:"storage_tier"`
	Tablespace    string             `json:"tablespace"`
	Lineage       *DataLineage       `json:"data_lineage,omitempty"`
	ApiEndpoints  []ApiEndpointRef   `json:"api_endpoints,omitempty"`
	ExampleCalls  []ExampleCall      `json:"example_calls,omitempty"`
	RelatedTables []CrossRef         `json:"related_tables,omitempty"`
	// Enhanced: per-source statistics (auto-discovered from DB)
	DataSources []DataSourceSummary `json:"data_sources,omitempty"`
	// Enhanced: capability description for LLM function-calling
	Capability *DataCapability `json:"capability,omitempty"`
	// Phase 2: aggregated field dictionary view. Present when the table is
	// registered in data_dataset_dictionary (i.e. governed by the field
	// dictionary). Combines the authoritative field contract with observed
	// JSONB key stats so callers get meaning + coverage + governance state
	// in one request.
	FieldDictionary *TableFieldDictionary `json:"field_dictionary,omitempty"`
}

// TableFieldDictionary is the table-level aggregated view of the field
// dictionary for a governed table. It is the union of the authoritative
// data_field_dictionary contract and the observed JSONB key statistics.
type TableFieldDictionary struct {
	Dataset         string                 `json:"dataset"`
	Source          string                 `json:"source"`
	ContractVersion string                 `json:"contract_version,omitempty"`
	Groups          []DictionaryFieldGroup `json:"groups"`
	// UngovernedKeys lists JSONB keys observed in the data but not registered
	// in data_field_dictionary. These are candidates for dictionary backfill
	// — typically SDK-added fields the dictionary has not caught up with.
	UngovernedKeys []string `json:"ungoverned_keys,omitempty"`
}

// DictionaryFieldGroup groups dictionary fields by data_type within a
// governed table (e.g. balance_sheet / income / cashflow for
// financial_statement).
type DictionaryFieldGroup struct {
	DataType string                `json:"data_type"`
	LabelZh  string                `json:"label_zh,omitempty"`
	Fields   []FieldDiscoveryEntry `json:"fields"`
}

// DataSourceSummary describes per-source statistics for a table.
// Auto-populated by querying GROUP BY source.
type DataSourceSummary struct {
	Source        string `json:"source"`
	RowCount      int64  `json:"row_count"`
	DistinctCodes int    `json:"distinct_codes"`
	MinDate       string `json:"min_date,omitempty"`
	MaxDate       string `json:"max_date,omitempty"`
}

// DataCapability describes what data a table/domain can provide.
// Designed for LLM function-calling tool registration — a compact
// machine-readable description of data availability and semantics.
type DataCapability struct {
	// Provider is a human-readable name, e.g. "财务报表 (三表+快报+预告)"
	Provider string `json:"provider"`
	// ProviderDescription explains what this data provides
	ProviderDescription string `json:"provider_description"`
	// DataTypes lists the sub-types available (e.g. ["balance_sheet","income","cashflow"])
	DataTypes []DataTypeInfo `json:"data_types,omitempty"`
	// OutputFields describes the structured output fields
	OutputFields []FieldDesc `json:"output_fields,omitempty"`
	// QueryParams describes how to query this data
	QueryParams []ParamDesc `json:"query_params,omitempty"`
	// RefreshSchedule describes how often data is refreshed
	RefreshSchedule string `json:"refresh_schedule,omitempty"`
	// CoverageDescription summarizes data coverage (e.g. "A股全量，2007至今")
	CoverageDescription string `json:"coverage_description,omitempty"`
}

// DataTypeInfo describes a sub-type within a table (e.g. statement_type="balance_sheet").
type DataTypeInfo struct {
	TypeValue   string `json:"type_value"`
	Label       string `json:"label"`
	Description string `json:"description"`
	Source      string `json:"source,omitempty"`
}

// FieldDesc describes an output field for capability discovery.
type FieldDesc struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
	InJSONB     bool   `json:"in_jsonb,omitempty"`
}

// ParamDesc describes a query parameter for capability discovery.
type ParamDesc struct {
	Name        string   `json:"name"`
	Type        string   `json:"type"`
	Required    bool     `json:"required"`
	Description string   `json:"description"`
	Enum        []string `json:"enum,omitempty"`
}

// DataCapabilities is the response for GET /api/v2/catalog/capabilities.
// A lightweight LLM-optimized view of data availability.
type DataCapabilities struct {
	GeneratedAt  time.Time          `json:"generated_at"`
	Capabilities []DomainCapability `json:"capabilities"`
}

// DomainCapability groups capabilities by business domain.
type DomainCapability struct {
	Domain      string            `json:"domain"`
	Label       string            `json:"label"`
	Description string            `json:"description"`
	Tables      []TableCapability `json:"tables"`
}

// TableCapability is a lightweight per-table capability summary.
type TableCapability struct {
	Schema      string              `json:"schema"`
	TableName   string              `json:"table_name"`
	Description string              `json:"description"`
	RowCount    int64               `json:"row_count"`
	TimeRange   *TimeRange          `json:"time_range,omitempty"`
	DataSources []DataSourceSummary `json:"data_sources,omitempty"`
	Capability  *DataCapability     `json:"capability,omitempty"`
}

// ColumnDictionary extends ColumnMeta with value-level metadata.
type ColumnDictionary struct {
	Name         string        `json:"name"`
	Type         string        `json:"type"`
	Nullable     bool          `json:"nullable"`
	IsPrimaryKey bool          `json:"is_primary_key"`
	Description  string        `json:"description,omitempty"`
	JSONBKeys    []JSONBKeyRef `json:"jsonb_keys,omitempty"`
	EnumValues   []string      `json:"enum_values,omitempty"`
}

// JSONBKeyRef describes a key found in a JSONB column.
type JSONBKeyRef struct {
	Name       string   `json:"name"`
	ValueType  string   `json:"value_type"`
	SampleVals []string `json:"sample_vals,omitempty"`
}
