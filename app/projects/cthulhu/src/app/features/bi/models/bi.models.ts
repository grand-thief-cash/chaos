// Lightweight BI models for the redesigned BI layer.
// cthulhu → artemis /bi/* → phoenixA /api/v2/*

export interface BISecurityItem {
  security_id: number;
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

// ─── Per-security coverage ───

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

export interface BISecurityCoverageResponse {
  generated_at: string;
  security_id: number;
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
  enum_ref?: string;
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

// ─── DuPont analysis ───
//
// Structured DuPont decomposition computed by artemis. Amounts are in yuan,
// ratios are 0-1 floats; the page formats them to 亿元 / %.

export type DupontDirection = 'up' | 'down' | 'flat';

export interface BIDupontMetricNode {
  code: string;
  label: string;
  value: number | null;
  prev_value: number | null;
  delta: number | null;
  direction: DupontDirection | null;
  unit: 'ratio' | 'amount_yuan';
  available: boolean;
  note: string | null;
}

export interface BIDupontTreeNode extends BIDupontMetricNode {
  children: BIDupontTreeNode[];
}

export interface BIDriverItem {
  label: string;
  value: number | null;
  prev_value: number | null;
  note: string;
  direction: DupontDirection | null;
  unit: 'ratio' | 'amount_yuan';
}

export interface BIDetailEquation {
  result_label: string;
  result_value: number | null;
  expression: string;
  note: string;
  unit: 'ratio' | 'amount_yuan';
}

export interface BIDetailStackRow {
  label: string;
  raw_field: string;
  value: number | null;
}

export interface BIDetailStack {
  title: string;
  total: number | null;
  accent: string;
  rows: BIDetailStackRow[];
}

export type DupontPeriodKind = 'annual' | 'single_quarter' | 'ytd' | 'ttm';

export interface BIDupontResponse {
  generated_at: string;
  security_id: number;
  symbol: string;
  source: string;
  market: string;
  report_type: string;
  statement_code: string;
  period: string;
  prev_period: string | null;
  security_name: string | null;
  period_kind: DupontPeriodKind;
  target_reporting_period: string;
  extrapolated_full_year: BIDupontResponse | null;
  headline_drivers: BIDriverItem[];
  tree: BIDupontTreeNode;
  nodes: Record<string, BIDupontMetricNode>;
  detail_equations: BIDetailEquation[];
  detail_stacks: BIDetailStack[];
  notes: string[];
}
