// Lightweight BI models for the redesigned BI layer.
// cthulhu → artemis /bi/* → phoenixA /api/v2/*

export interface BISecurityItem {
  symbol: string;
  asset_type: string;
  market: string;
  exchange: string;
  name: string;
  full_name?: string | null;
  status: string;
  list_date?: string | null;
  delist_date?: string | null;
}

export interface BISecuritiesResponse {
  items: BISecurityItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BIDatasetEntry {
  source: string;
  dataset: string;
  label_zh: string;
  data_types: string[];
  storage_table: string;
  source_doc: string;
  field_discovery: string;
  query: string;
}

export interface BIDatasetsResponse {
  generated_at: string;
  contract_version: string;
  datasets: BIDatasetEntry[];
}

export interface BIFieldDiscoveryEntry {
  raw_field: string;
  canonical_field: string;
  label_zh: string;
  description: string;
  value_type: string;
  unit: string;
  scale: number | null;
  enum_ref: string;
  storage_location: 'top_level' | 'data_json';
  query_name: string;
  is_metadata: boolean;
  is_core: boolean;
  aliases: string[];
  source_doc: string;
}

export interface BIFieldDiscoveryResponse {
  generated_at: string;
  dataset: string;
  source: string;
  data_type: string;
  contract_version: string;
  fields: BIFieldDiscoveryEntry[];
}

export interface BIEnumResponse {
  generated_at: string;
  enum_name: string;
  values: { code: string; label_zh: string }[];
}

// ─── Per-symbol coverage ───

export interface BICoverageReportTypeBucket {
  report_type: string;
  row_count: number;
  earliest_period: string;
  latest_period: string;
  latest_ann_date: string;
}

export interface BICoverageDataType {
  data_type: string;
  total_rows: number;
  earliest_period: string;
  latest_period: string;
  latest_ann_date: string;
  by_report_type?: BICoverageReportTypeBucket[];
}

export interface BICoverageDataset {
  dataset: string;
  source: string;
  data_types: BICoverageDataType[];
}

export interface BISymbolCoverageResponse {
  generated_at: string;
  symbol: string;
  market: string;
  datasets: BICoverageDataset[];
}

// ─── Raw query ───

export interface BIFieldMeta {
  name: string;
  raw_field: string;
  canonical_field: string;
  label_zh: string;
  value_type: string;
  unit: string;
  scale: number | null;
  storage_location: string;
  is_metadata: boolean;
  is_core: boolean;
}

export interface BIRawQueryResponse {
  generated_at: string;
  dataset: string;
  source: string;
  data_type: string;
  rows: Record<string, string | number | null>[];
  fields: BIFieldMeta[];
  total: number;
  page: number;
  page_size: number;
}
