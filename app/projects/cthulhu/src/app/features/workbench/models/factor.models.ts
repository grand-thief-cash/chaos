/** Factor meta from /factors/meta */
export interface FactorMeta {
  name: string;
  cn_name: string;
  category: string;
  formula: string;
  unit: string;
  higher_is_better: boolean;
  requires_market_data: boolean;
  exclude_financial: boolean;
}

/** Response from /factors/snapshot */
export interface FactorSnapshot {
  raw_factors: Record<string, number>;
  norm_factors: Record<string, number>;
  meta: Record<string, string>;
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

