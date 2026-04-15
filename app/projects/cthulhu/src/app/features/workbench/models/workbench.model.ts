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
  symbol: string;
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

// ===== 策略相关 =====

export interface StrategyParamSchema {
  type: 'int' | 'float' | 'string' | 'bool';
  min?: number;
  max?: number;
  required?: boolean;
}

export interface WorkbenchStrategy {
  code: string;
  default_params: Record<string, any>;
  supported_modes: string[];
  supported_periods: string[];
  param_schema: Record<string, StrategyParamSchema>;
}

export interface WorkbenchStrategiesResponse {
  strategies: WorkbenchStrategy[];
}

// ===== 请求 =====

export interface WorkbenchRunRequest {
  strategy_code: string;
  symbol: string;
  start_date: string;
  end_date: string;
  period: string;
  adjust: string;
  asset_type: string;
  market: string;
  cash: number;
  commission: number;
  strategy_params: Record<string, any>;
  source?: string;
}

// ===== 响应 =====

export interface EquityPoint {
  timestamp: string;
  close: number;
  cash: number;
  value: number;
}

export interface SignalEvent {
  timestamp: string;
  signal: 'BUY' | 'SELL';
  close: number;
}

export interface TradeEvent {
  timestamp: string;
  size: number;
  price: number;
  pnl: number;
  pnlcomm: number;
  barlen: number;
}

export interface OrderEvent {
  timestamp: string;
  status: string;
  order_type: 'BUY' | 'SELL';
  size: number;
  price: number;
  value: number;
  commission: number;
}

export interface BacktestSummary {
  strategy_code: string;
  symbol: string;
  period: string;
  start_date: string;
  end_date: string;
  start_cash: number;
  end_value: number;
  pnl: number;
  pnl_pct: number;
  max_drawdown: number;
  sharpe: number;
  bars_processed: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
}

export interface BacktestArtifacts {
  equity_curve: EquityPoint[];
  return_curve: ReturnPoint[];
  signals: SignalEvent[];
  trades: TradeEvent[];
  orders: OrderEvent[];
  positions: any[];
  bars?: Bar[];
}

export interface ReturnPoint {
  timestamp: string;
  return_pct: number;
}

export interface BacktestResult {
  run_meta: { run_id: string; parent_run_id: string | null; task_code: string };
  summary: BacktestSummary;
  artifacts: BacktestArtifacts;
}
