export type DisplayKind = 'amount' | 'ratio' | 'pct_point' | 'count';
export type WarningSeverity = 'low' | 'medium' | 'high';

export interface BIIndustryMeta {
  taxonomy: string;
  level: number;
  code: string;
  name: string;
  index_code: string;
}

export interface BICompanyMeta {
  symbol: string;
  name: string;
  market: string;
  exchange: string;
  industry: BIIndustryMeta;
  comp_type_code: number;
  financial_sector: boolean;
}

export interface BISecuritySearchItem {
  symbol: string;
  name: string;
  exchange: string;
  market: string;
  asset_type: string;
  status: string;
}

export interface BISecuritySearchResponse {
  query: string;
  market: string;
  total: number;
  items: BISecuritySearchItem[];
}

export interface BIMetricValue {
  code: string;
  label: string;
  unit: string;
  display_kind: DisplayKind;
  value: number | null;
  same_period_last_year: number | null;
  yoy_delta: number | null;
  yoy_growth?: number | null;
  data_period: string;
  source_fields: string[];
  available: boolean;
  degraded: boolean;
  notes: string[];
}

export interface BITrendSeries {
  code: string;
  label: string;
  values: Array<number | null>;
}

export interface BITrendSection {
  code: string;
  title: string;
  periods: string[];
  series: BITrendSeries[];
}

export interface BISummaryCard {
  code: string;
  title: string;
  items: BIMetricValue[];
}

export interface BIWarning {
  code: string;
  severity: WarningSeverity;
  title: string;
  message: string;
  evidence_metric_codes: string[];
}

export interface BISourceNote {
  section: string;
  statement_types: string[];
  pit_rule: string;
  metric_version: string;
}

export interface BIDashboardResponse {
  symbol: string;
  as_of_date: string;
  latest_period: string;
  company: BICompanyMeta;
  kpis: BIMetricValue[];
  trend_sections: BITrendSection[];
  summary_cards: BISummaryCard[];
  warnings: BIWarning[];
  source_notes: BISourceNote[];
}

export interface BIDupontNode {
  code: string;
  label: string;
  metric: BIMetricValue;
  children: BIDupontNode[];
}

export interface BIDriverSummaryItem {
  driver: string;
  direction: 'up' | 'down' | 'flat';
  message: string;
}

export interface BIDupontComparisonRow {
  period: string;
  roe: number | null;
  net_margin: number | null;
  asset_turnover: number | null;
  equity_multiplier: number | null;
}

export interface BIDupontResponse {
  symbol: string;
  as_of_date: string;
  latest_period: string;
  company: BICompanyMeta;
  headline_metrics: Record<string, BIMetricValue>;
  dupont_tree: BIDupontNode;
  trend_sections: BITrendSection[];
  driver_summary: BIDriverSummaryItem[];
  comparison_rows: BIDupontComparisonRow[];
}

export interface BIQualityTableRow {
  period: string;
  values: Record<string, number | null>;
}

export interface BIQualityPanel {
  code: string;
  title: string;
  metrics: BIMetricValue[];
  trend_sections: BITrendSection[];
  table_rows: BIQualityTableRow[];
  warnings: BIWarning[];
}

export interface BIQualityResponse {
  symbol: string;
  as_of_date: string;
  latest_period: string;
  company: BICompanyMeta;
  panels: BIQualityPanel[];
  source_notes: BISourceNote[];
}

export interface BIPeerComparisonRequest {
  symbols?: string[];
  industry_code?: string;
  as_of_date: string;
  market?: string;
  source?: string;
  metrics?: string[];
  limit?: number;
}

export interface BIPeerComparisonRow {
  symbol: string;
  company_name: string;
  industry_name: string;
  metrics: Record<string, BIMetricValue>;
}

export interface BIPeerComparisonResponse {
  as_of_date: string;
  market: string;
  industry_code: string;
  requested_metrics: string[];
  rows: BIPeerComparisonRow[];
}

export interface BIInsightHighlight {
  code: string;
  title: string;
  message: string;
  related_metrics: string[];
}

export interface BIInsightResponse {
  symbol: string;
  as_of_date: string;
  latest_period: string;
  company: BICompanyMeta;
  headline: string;
  structured_highlights: BIInsightHighlight[];
  anomalies: BIWarning[];
  trend_summary: string[];
  source_notes: BISourceNote[];
}

export interface BIMetricDefinition {
  code: string;
  label: string;
  category: string;
  display_kind: DisplayKind;
  unit: string;
  formula: string;
  source_fields: string[];
  applicable_comp_types: number[];
  phase: string;
  available: boolean;
}

export interface BIMetricsMetaResponse {
  version: string;
  metrics: BIMetricDefinition[];
}


