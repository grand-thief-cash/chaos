export interface BufferStats {
  key: string;
  category: string;
  submitted_rows: number;
  flushed_rows: number;
  pending_items: number;
  flush_count: number;
}

export interface WriteBufferStatus {
  enabled: boolean;
  buffers: BufferStats[];
}

// ─── Data Catalog Models ───

export interface CatalogOverview {
  generated_at: string;
  cached: boolean;
  cache_ttl_seconds: number;
  summary: CatalogSummary;
  storage_tiers: Record<string, TierSummary>;
  domains: DomainCatalogSummary[];
}

export interface CatalogSummary {
  total_tables: number;
  total_rows: number;
  total_disk_size: string;
  total_disk_size_bytes: number;
  total_index_size: string;
  total_index_size_bytes: number;
}

export interface TierSummary {
  tablespace: string;
  disk_size: string;
  disk_size_bytes: number;
  table_count: number;
}

export interface DomainCatalogSummary {
  domain: string;
  description: string;
  table_count: number;
  total_rows: number;
  total_disk_size: string;
  total_disk_size_bytes: number;
}

export interface TableCatalogEntry {
  schema: string;
  table_name: string;
  domain: string;
  description: string;
  row_count: number;
  disk_size: string;
  disk_size_bytes: number;
  index_size: string;
  index_size_bytes: number;
  tablespace: string;
  storage_tier: string;
  is_hypertable: boolean;
  time_range?: TimeRange;
  last_modified?: string;
  column_count: number;
  has_jsonb: boolean;
}

export interface TimeRange {
  column: string;
  min: string;
  max: string;
}

export interface TableDetail extends TableCatalogEntry {
  columns: ColumnMeta[];
  indexes: IndexMeta[];
  data_lineage?: DataLineage;
}

export interface ColumnMeta {
  name: string;
  type: string;
  nullable: boolean;
  description?: string;
  is_primary_key?: boolean;
  jsonb_keys?: Record<string, string[]> | string[];
}

export interface IndexMeta {
  name: string;
  columns: string[];
  is_unique: boolean;
  type?: string;
}

export interface DataLineage {
  source_system: string;
  ingestion_method: string;
  refresh_schedule: string;
  api_endpoint?: string;
}

export interface StorageInfo {
  tablespaces: TablespaceInfo[];
}

export interface TablespaceInfo {
  name: string;
  location: string;
  tier: string;
  hardware: string;
  total_size: string;
  total_size_bytes: number;
  table_count: number;
  tables: string[];
}

// ─── Neo4j Graph Catalog Models ───

export interface GraphCatalogOverview {
  available: boolean;
  node_counts?: Record<string, number>;
  total_nodes: number;
  total_edges: number;
  labels?: GraphLabelInfo[];
  rel_types?: GraphRelTypeInfo[];
}

export interface GraphLabelInfo {
  label: string;
  count: number;
  description?: string;
}

export interface GraphRelTypeInfo {
  type: string;
  count: number;
  description?: string;
}


