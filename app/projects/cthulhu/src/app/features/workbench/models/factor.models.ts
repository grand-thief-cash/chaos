/** Factor meta from /factors/meta */
export interface FactorPhoenixQuery {
  endpoint: string;
  source?: string;
  statement_type?: string;
  action_type?: string;
  asset_type?: string;
  market?: string;
  params?: string[];
  fields?: string[];
  notes?: string;
}

export interface FactorFinancialPolicy {
  mode: string;
  action?: string;
  reason?: string;
  future_variant?: string;
}

export interface FactorAvailability {
  expected: string;
  requirements?: string[];
  runtime_state?: string;
}

export interface FactorFreshness {
  latest_reporting_period?: string;
  latest_ann_date?: string;
  as_of_date?: string;
  staleness_days?: number;
  freshness_score?: number;
  freshness_label?: string;
}

export interface FactorSnapshotMeta {
  version?: string;
  industry_code?: string;
  company_kind?: string;
  reporting_period?: string;
  latest_ann_date?: string;
  freshness?: FactorFreshness;
  missing_reasons?: Record<string, string>;
  incremental?: boolean;
}

export interface FactorAvailabilitySourceDetail {
  available: boolean;
  status?: string;
  sources?: Record<string, number>;
  time_range?: Record<string, string> | null;
  fields_known?: string[];
  data_types?: string[];
  row_count?: number;
  notes?: string[];
}

export interface FactorAvailabilityProvenance {
  source_fields?: string[];
  phoenix_queries?: FactorPhoenixQuery[];
  required_data_sources?: string[];
}

export interface FactorAvailabilityItem {
  name: string;
  cn_name: string;
  category: string;
  availability_expected: string;
  availability_status: string;
  required_data_sources: string[];
  required_fields: string[];
  required_field_count: number;
  available_sources: string[];
  missing_sources: string[];
  unknown_sources?: string[];
  missing_fields?: string[];
  unknown_fields?: string[];
  source_status: Record<string, FactorAvailabilitySourceDetail>;
  provenance?: FactorAvailabilityProvenance;
  notes?: string[];
}

export interface FactorAvailabilitySummary {
  available?: number;
  partial?: number;
  missing?: number;
  unknown?: number;
}

export interface FactorAvailabilityResponse {
  capability_source: string;
  capability_error?: string;
  capability_http_status?: number;
  selected_source?: string;
  source_status: Record<string, FactorAvailabilitySourceDetail>;
  summary: FactorAvailabilitySummary;
  factors: FactorAvailabilityItem[];
}

export interface FactorMeta {
  name: string;
  cn_name: string;
  category: string;
  formula: string;
  unit: string;
  data_sources?: string[];
  higher_is_better: boolean;
  requires_market_data: boolean;
  exclude_financial: boolean;
  ttm_required?: boolean;
  min_history_quarters?: number;
  description?: string;
  latex_formula?: string;
  management_phase?: string;
  status?: string;
  management_tags?: string[];
  source_fields?: string[];
  phoenix_queries?: FactorPhoenixQuery[];
  financial_policy?: FactorFinancialPolicy;
  availability?: FactorAvailability;
  governance?: Record<string, unknown>;
  catalog_version?: string;
  catalog_seeded?: boolean;
}

/** Response from /factors/snapshot */
export interface FactorSnapshot {
  raw_factors: Record<string, number>;
  norm_factors: Record<string, number>;
  meta: FactorSnapshotMeta;
}

/** Response from /factors/rank */
export interface FactorRankItem {
  symbol: string;
  [factorName: string]: string | number;
}

/** Response from /factors/compute/full and /factors/compute/incremental */
export interface FactorComputeResult {
  status: string;
  symbols_count: number;
  as_of_date?: string;
}

