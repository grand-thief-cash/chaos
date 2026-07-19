// ===== 数据维度选项 =====

export interface DataOption {
  value: string;
  label: string;
}

export interface AdjustRule {
  asset_type: string;
  options: DataOption[];
}

export interface DataOptionsResponse {
  asset_types: DataOption[];
  markets: DataOption[];
  periods: DataOption[];
  adjust_rules: AdjustRule[];
}

// ===== 市场数据相关 =====

export interface SourcesResponse {
  sources: string[];
  current: string;
}

export interface Bar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount?: number;
}

export interface MarketDataResponse {
  security_id: number;
  symbol: string;
  period: string;
  start_date: string;
  end_date: string;
  bars: Bar[];
}

export interface IndicatorInfo {
  name: string;
  display_name: string;
  default_params: Record<string, any>;
  overlay: boolean;
  y_axis: string | null;
}

export interface IndicatorsListResponse {
  indicators: IndicatorInfo[];
}

export interface IndicatorRequest {
  name: string;
  params: Record<string, any>;
}

export interface IndicatorsCalcRequest {
  security_id: number;
  start_date: string;
  end_date: string;
  period: string;
  adjust: string;
  asset_type: string;
  market: string;
  indicators: IndicatorRequest[];
  source?: string;
}

export interface IndicatorsCalcResponse {
  security_id: number;
  symbol: string;
  period: string;
  indicators: Record<string, (number | null)[]>;
  indicator_meta: Record<string, IndicatorSeriesMeta>;
}

export interface IndicatorSeriesMeta {
  type: 'line' | 'bar';
  color: string | string[];
  overlay: boolean;
  y_axis?: string;
}
