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

// ===== T-trading replay (ephemeral; never persisted) =====

export interface TStrategyConfig {
  direction: 'buy_first' | 'sell_first';
  window: number;
  entry_z: number;
  exit_z: number;
  entry_rsi: number;
  exit_rsi: number;
  confirmation_bars: number;
  cooldown_bars: number;
  max_round_trips: number;
}

export interface TExecutionConfig {
  quantity: number;
  commission_rate: number;
  minimum_commission: number;
  stamp_duty_rate_on_sell: number;
  transfer_fee_rate: number;
  slippage_bps: number;
}

export interface TReplayRequest {
  security_id: number;
  trade_date: string;
  period: 'min5';
  adjust: 'nf';
  source?: string;
  persistence_mode: 'ephemeral';
  strategy: TStrategyConfig;
  execution: TExecutionConfig;
}

export interface TSignal {
  signal_id: string;
  bar_index: number;
  decision_time: string;
  side: 'BUY' | 'SELL';
  decision_price: number;
  confidence: number;
  reason_codes: string[];
  features: Record<string, number | null>;
}

export interface TFill {
  fill_id: string;
  signal_id: string;
  bar_index: number;
  fill_time: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  raw_open_price: number;
  fill_price: number;
  notional: number;
  slippage_cost: number;
  commission: number;
  stamp_duty: number;
  transfer_fee: number;
  total_fee: number;
}

export interface TRoundTrip {
  round_trip_id: string;
  open_fill_id: string;
  close_fill_id: string;
  direction: 'buy_first' | 'sell_first';
  open_time: string;
  close_time: string;
  quantity: number;
  gross_pnl: number;
  total_fee: number;
  net_pnl: number;
  return_pct: number;
  mfe: number;
  mae: number;
  win: boolean;
}

export interface TReplaySummary {
  round_trips: number;
  wins: number;
  losses: number;
  win_rate: number;
  gross_pnl: number;
  total_fee: number;
  net_pnl: number;
  average_return_pct: number;
  best_return_pct: number;
  worst_return_pct: number;
  profit_factor: number | null;
  replay_days?: number;
  days_with_trades?: number;
  signal_count?: number;
  fill_count?: number;
}

export interface TReplayResponse {
  run_meta: {
    run_id: string;
    security_id: number;
    symbol: string;
    trade_date: string;
    period: string;
    adjust: string;
    persistence_mode: 'ephemeral';
    causality: string;
  };
  bars: Bar[];
  signals: TSignal[];
  fills: TFill[];
  round_trips: TRoundTrip[];
  summary: TReplaySummary;
  data_quality: {
    bar_count: number;
    zero_volume_bars: number;
    unexpected_gap_count: number;
    first_bar_time: string;
    last_bar_time: string;
  };
}

export interface TBatchReplayRequest {
  security_ids: number[];
  start_date: string;
  end_date: string;
  period: 'min5';
  adjust: 'nf';
  source?: string;
  persistence_mode: 'ephemeral';
  strategy: TStrategyConfig;
  execution: TExecutionConfig;
  include_details?: boolean;
}

export interface TBatchReplayResponse {
  run_meta: { run_id: string; start_date: string; end_date: string; period: string; persistence_mode: 'ephemeral' };
  summary: TReplaySummary;
  by_security: Array<TReplaySummary & { security_id: number }>;
  by_day: Array<TReplaySummary & { trade_date: string }>;
  results: Array<TReplayResponse | { run_meta: TReplayResponse['run_meta']; summary: TReplaySummary; data_quality: TReplayResponse['data_quality'] }>;
  skipped: Array<{ security_id: number; trade_date: string; reason: string }>;
  failures: Array<{ security_id: number; trade_date: string; error_type: string; reason: string }>;
}
