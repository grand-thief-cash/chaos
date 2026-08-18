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

export type TStrategyName =
  | 'causal_mean_reversion_v1'
  | 'macd_volume_momentum_v1'
  | 'macd_volume_regime_reversal_v1'
  | 'vwap_bollinger_reversion_v1'
  | 'opening_range_breakout_v1'
  | 'time_of_day_volume_momentum_v1'
  | 'market_residual_reversal_v1'
  | 'multi_timeframe_pullback_v1';

export type TSignalMode = 'buy_first' | 'sell_first' | 'independent';

export interface TStrategyConfig {
  strategy: TStrategyName;
  direction: TSignalMode;
  window: number;
  entry_z: number;
  exit_z: number;
  entry_rsi: number;
  exit_rsi: number;
  confirmation_bars: number;
  cooldown_bars: number;
  max_round_trips: number;
  ema_fast: number;
  ema_slow: number;
  macd_signal: number;
  min_volume_ratio: number;
  ema_deviation_atr: number;
  macd_turn_bars: number;
  volume_confirmation_window: number;
  panic_window_bars: number;
  panic_return_threshold: number;
  panic_volume_ratio: number;
  macd_divergence_lookback: number;
  rebound_confirmation_bars: number;
  rebound_recovery_ratio: number;
  deep_reversal_min_score: number;
  regime_slope_bars: number;
  medium_trend_fast_bars: number;
  medium_trend_slow_bars: number;
  rebound_ema_tolerance_atr: number;
  minimum_recent_range: number;
  bollinger_z: number;
  reversal_wick_ratio: number;
  max_trend_strength_atr: number;
  atr_window: number;
  opening_range_bars: number;
  breakout_atr_buffer: number;
  relative_volume_tod_threshold: number;
  min_time_of_day_history_days: number;
  market_beta_window: number;
  residual_z_threshold: number;
  higher_ema_fast: number;
  higher_ema_slow: number;
  daily_trend_window: number;
  pullback_tolerance_atr: number;
}

export interface TSignalEvaluationConfig {
  horizons_bars: number[];
  primary_horizon_bars: number;
  target_return: number;
  stop_return: number;
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
  period: 'min1' | 'min5';
  adjust: 'nf';
  source?: string;
  persistence_mode: 'ephemeral';
  strategy: TStrategyConfig;
  strategies?: TStrategyConfig[];
  benchmark_security_id?: number;
  evaluation: TSignalEvaluationConfig;
  include_execution_simulation: boolean;
  execution: TExecutionConfig;
}

export interface TSignal {
  signal_id: string;
  bar_index: number;
  decision_time: string;
  side: 'BUY' | 'SELL';
  decision_price: number;
  strategy: TStrategyConfig['strategy'];
  confidence: number;
  confidence_kind: 'rule_score_v2';
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

export interface TSignalEvaluationSummary {
  horizon_bars: number;
  side: 'ALL' | 'BUY' | 'SELL';
  signal_count: number;
  evaluable_signal_count: number;
  insufficient_future_count: number;
  directional_accuracy: number | null;
  mean_directional_return: number | null;
  median_directional_return: number | null;
  mean_mfe: number | null;
  median_mfe: number | null;
  mean_mae: number | null;
  median_mae: number | null;
  edge_ratio: number | null;
  target_touch_rate: number | null;
  stop_touch_rate: number | null;
  target_first_rate: number | null;
  stop_first_rate: number | null;
  ambiguous_same_bar_rate: number | null;
  replay_days?: number;
  days_with_signals?: number;
  strategy?: TStrategyName | null;
}

export interface TSignalOutcome {
  signal_id: string;
  strategy: TStrategyConfig['strategy'];
  side: 'BUY' | 'SELL';
  decision_time: string;
  decision_price: number;
  horizon_bars: number;
  evaluable: boolean;
  reason?: string;
  directional_return?: number;
  direction_correct?: boolean;
  mfe?: number;
  mae?: number;
  time_to_mfe_bars?: number;
  time_to_mae_bars?: number;
  target_touched?: boolean;
  stop_touched?: boolean;
  first_touch?: 'target_first' | 'stop_first' | 'ambiguous_same_bar' | 'no_touch';
  first_touch_bar?: number | null;
}

export interface TSignalEvaluation {
  evaluation_kind: 'forward_event_study_v1';
  price_basis: 'decision_bar_close';
  future_window: 'bars_after_decision';
  same_bar_touch_policy: 'ambiguous';
  config: TSignalEvaluationConfig;
  summary: TSignalEvaluationSummary;
  by_horizon: Array<TSignalEvaluationSummary & {
    by_side: { BUY: TSignalEvaluationSummary; SELL: TSignalEvaluationSummary };
  }>;
  by_strategy: Array<TSignalEvaluationSummary & { strategy: TStrategyName }>;
  by_strategy_side: Array<TSignalEvaluationSummary & { strategy: TStrategyName }>;
  outcomes: TSignalOutcome[];
}

export interface SecuritiesSearchItem {
  security_id: number;
  exchange: string;
  asset_type: string;
  symbol: string;
  market: string;
  name: string;
  status: string;
}

export interface SecuritiesSearchResponse {
  items: SecuritiesSearchItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TNearestTradeDateResponse {
  security_id: number;
  requested_trade_date: string;
  direction: 'prev' | 'next';
  trade_date: string;
  available_count: number;
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
    engine_version: string;
    strategies: TStrategyName[];
  };
  bars: Bar[];
  indicator_sets: TIndicatorSet[];
  signals: TSignal[];
  signal_evaluation: TSignalEvaluation;
  fills: TFill[];
  round_trips: TRoundTrip[];
  summary: TSignalEvaluationSummary;
  execution_summary: {
    enabled: boolean;
    round_trips: number;
    wins: number;
    losses: number;
    win_rate: number;
    gross_pnl: number;
    total_fee: number;
    net_pnl: number;
  };
  data_quality: {
    bar_count: number;
    zero_volume_bars: number;
    unexpected_gap_count: number;
    first_bar_time: string;
    last_bar_time: string;
    strategy_context?: Record<string, unknown>;
  };
}

export interface TIndicatorPoint {
  date: string;
  ema_fast: number | null;
  ema_slow: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  macd_hist_delta: number | null;
  macd_hist_rising_bars: number | null;
  macd_hist_falling_bars: number | null;
  ema_deviation_atr: number | null;
  recent_volume_ratio_max: number | null;
  vwap: number | null;
  rsi: number | null;
  volume_ratio: number | null;
  relative_volume_tod: number | null;
  bollinger_upper: number | null;
  bollinger_lower: number | null;
  opening_range_high: number | null;
  opening_range_low: number | null;
}

export interface TIndicatorSet {
  strategy: TStrategyName;
  parameters: TStrategyConfig;
  points: TIndicatorPoint[];
}

export interface TBatchReplayRequest {
  security_ids: number[];
  start_date: string;
  end_date: string;
  period: 'min1' | 'min5';
  adjust: 'nf';
  source?: string;
  persistence_mode: 'ephemeral';
  strategy: TStrategyConfig;
  strategies?: TStrategyConfig[];
  benchmark_security_id?: number;
  evaluation: TSignalEvaluationConfig;
  include_execution_simulation: boolean;
  execution: TExecutionConfig;
  include_details?: boolean;
}

export interface TBatchReplayResponse {
  run_meta: { run_id: string; start_date: string; end_date: string; period: string; persistence_mode: 'ephemeral' };
  summary: TSignalEvaluationSummary;
  by_strategy: Array<TSignalEvaluationSummary & { strategy: TStrategyName }>;
  by_security: Array<TSignalEvaluationSummary & { security_id: number }>;
  by_day: Array<TSignalEvaluationSummary & { trade_date: string }>;
  results: Array<TReplayResponse | { run_meta: TReplayResponse['run_meta']; summary: TSignalEvaluationSummary; data_quality: TReplayResponse['data_quality'] }>;
  skipped: Array<{ security_id: number; trade_date: string; reason: string }>;
  failures: Array<{ security_id: number; trade_date: string; error_type: string; reason: string }>;
}

// ===== Point-in-time valuation matrix =====

export type ValuationScenario = 'bear' | 'base' | 'bull';
export type ValuationMethodCode = 'forward_pe' | 'pb_roe' | 'ev_ebitda' | 'dcf';
export type ValuationMethodRole = 'primary' | 'cross_check' | 'guardrail' | 'blended';

export interface ValuationAnalyzeRequest {
  security_id: number;
  valuation_date?: string;
  horizon_years: number;
  history_years: number;
  methods: ValuationMethodCode[];
  financial_source?: string;
  statement_code?: string;
}

export interface ValuationMethodResult {
  code: ValuationMethodCode;
  label: string;
  weight: number;
  role: ValuationMethodRole;
  included_in_headline: boolean;
  prices: Partial<Record<ValuationScenario, number>>;
  formula: string;
  calculation_trace?: Partial<Record<ValuationScenario, Record<string, any>>>;
  inputs: Record<string, any>;
  provenance: Record<string, any>;
}

export interface ValuationAnalyzeResponse {
  security: { security_id: number; symbol: string; name: string; exchange: string };
  valuation_date: string;
  price_as_of: string;
  market_price: number;
  horizon_years: number;
  range: Partial<Record<ValuationScenario, number>> & {
    upside_base: number;
    market_position: 'below_range' | 'inside_range' | 'above_range';
  };
  matrix: {
    scenarios: ValuationScenario[];
    scenario_definitions: Record<ValuationScenario, {
      label: string;
      semantics: 'low_consensus' | 'base_consensus' | 'high_consensus';
      tail_stress: boolean;
      description: string;
    }>;
    methods: ValuationMethodResult[];
    unavailable_methods: Array<{ code: ValuationMethodCode; reason: string }>;
    combined: Partial<Record<ValuationScenario, number>>;
    weights: Record<ValuationMethodCode, number>;
    weight_profile: 'balanced' | 'high_growth';
    weight_rationale: string;
    aggregation: {
      mode: 'primary_with_cross_checks' | 'weighted_blend' | 'single_method';
      primary_method: ValuationMethodCode | null;
      headline: Partial<Record<ValuationScenario, number>>;
      blended_reference: Partial<Record<ValuationScenario, number>>;
      method_roles: Partial<Record<ValuationMethodCode, ValuationMethodRole>>;
      cross_check_methods: ValuationMethodCode[];
      guardrail_methods: ValuationMethodCode[];
      rationale: string;
    };
  };
  forward_pe_sensitivity: {
    eps: Partial<Record<ValuationScenario, number>>;
    multiples: Partial<Record<ValuationScenario, number>>;
    grid: Partial<Record<ValuationScenario, Partial<Record<ValuationScenario, number>>>>;
    market_implied: {
      market_price: number;
      forward_pe_at_base_eps: number | null;
      eps_at_base_multiple: number | null;
      nearest_grid_cell: {
        eps_scenario: ValuationScenario;
        multiple_scenario: ValuationScenario;
        price: number;
        absolute_gap: number;
        gap_percent: number;
      };
    };
  } | null;
  price_reference: {
    framework: 'scenario_reference_not_target_price';
    state: 'below_low_consensus' | 'between_low_and_base' | 'between_base_and_high' | 'above_high_consensus';
    state_label: string;
    interpretation: string;
    anchors: {
      low_consensus: number;
      base_consensus: number;
      high_consensus: number;
      market_price: number;
    };
    market_implied: {
      market_price: number;
      forward_pe_at_base_eps: number | null;
      eps_at_base_multiple: number | null;
      nearest_grid_cell: {
        eps_scenario: ValuationScenario;
        multiple_scenario: ValuationScenario;
        price: number;
        absolute_gap: number;
        gap_percent: number;
      };
    } | null;
    tail_stress_available: boolean;
    tail_stress_note: string;
    usage_rules: string[];
  } | null;
  diagnostics: {
    pe_pb_coherence: {
      identity: string;
      status: 'unavailable' | 'aligned' | 'divergent' | 'severely_divergent';
      rows: Partial<Record<ValuationScenario, {
        eps: number;
        bvps: number;
        implied_roe: number;
        pe: number;
        coherent_pb: number;
        observed_pb_anchor: number;
        pb_gap_ratio: number;
      }>>;
      base_gap_ratio: number | null;
      interpretation: string;
    } | null;
  };
  fundamentals: Record<string, any>;
  confidence: {
    score: number;
    label: 'low' | 'medium' | 'high';
    usage_status: 'provisional' | 'limited';
    usage_label: string;
    score_semantics: string;
    decision_use: 'scenario_reference_only';
    gates: Array<{ code: string; score_cap: number; reason: string }>;
    dimensions: Array<{
      code: string;
      label: string;
      status: 'high' | 'medium' | 'low' | 'provisional' | 'limited' | 'unavailable';
      reason: string;
    }>;
    components: Array<{
      code: string;
      label: string;
      score: number;
      max_score: number;
      reason: string;
    }>;
  };
  warnings: Array<{ code: string; message: string }>;
  point_in_time: {
    information_as_of: string;
    price_as_of: string;
    price_source: string;
    financial_available_at: string | null;
    financial_reporting_period: string | null;
      consensus_as_of: string | null;
      consensus_source: string | null;
      consensus_latest_report_date: string | null;
      consensus_latest_report_age_days: number | null;
      target_fiscal_year: number;
    history_start: string | null;
    rule: string;
  };
}

export interface ValuationHistoryRequest {
  security_id: number;
  start_date: string;
  end_date: string;
  interval: 'month_end' | 'quarter_end';
  history_years: number;
}

export interface ValuationHistoryPoint {
  valuation_date: string;
  price_as_of: string;
  market_price: number;
  bear: number | null;
  base: number | null;
  bull: number | null;
  upside_base: number | null;
  confidence: { score: number; label: string };
  warning_codes: string[];
}

export interface ValuationHistoryResponse {
  security: { security_id: number; symbol?: string; name?: string };
  start_date: string;
  end_date: string;
  interval: string;
  points: ValuationHistoryPoint[];
  skipped: Array<{ valuation_date: string; reason: string }>;
  point_in_time: boolean;
}
