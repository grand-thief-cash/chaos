/** Regime state from /regime/current and /regime/history */
export interface RegimeResult {
  trade_date: string;

  // 6 core dimensions (0.0–1.0)
  trend_strength: number;
  risk_appetite: number;
  volatility_stress: number;
  market_breadth: number;
  liquidity: number;
  sector_concentration: number;

  // transition signals (-1.0 ~ +1.0)
  breadth_momentum: number;
  vol_acceleration: number;

  // derived labels
  label_market?: string;
  label_vol?: string;
  label_confidence?: string;

  // strategy allocation
  strategy_weights?: Record<string, number>;
  factor_weight_adjustments?: Record<string, number>;
  position_limit?: number;
  suggested_holding_period?: string;
}

/** Regime features from /regime/features */
export interface RegimeFeatures {
  trade_date: string;
  hs300_distance_from_ma120: number;
  hs300_ma20_slope: number;
  breadth_above_ma20_pct: number;
  vol_20d: number;
  vol_ratio: number;
  turnover_ratio: number;
  style_small_vs_large: number;
  industry_concentration: number;
}

/** Response from /regime/compute and /regime/backfill */
export interface RegimeComputeResult {
  status?: string;
  count?: number;
  [key: string]: any;
}

