"""因子标准化 — 去极值 / 行业 Z-Score / 市值中性化。"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


class FactorNormalizer:
    """因子标准化处理器。"""

    def __init__(self) -> None:
        self._industry_stats: Dict[str, Dict[str, Dict]] = {}

    # ------------------------------------------------------------------
    # 去极值 (MAD Winsorization)
    # ------------------------------------------------------------------
    @staticmethod
    def winsorize_mad(series: pd.Series, n: float = 5.0) -> pd.Series:
        """MAD 去极值。MAD = 0 时不做截断。"""
        valid = series.dropna()
        if len(valid) < 3:
            return series

        median = valid.median()
        mad = (valid - median).abs().median()

        if mad < 1e-10:
            return series  # 所有值几乎相同

        mad_scaled = 1.4826 * mad  # MAD → σ 等效
        upper = median + n * mad_scaled
        lower = median - n * mad_scaled
        return series.clip(lower, upper)

    # ------------------------------------------------------------------
    # 行业 Z-Score
    # ------------------------------------------------------------------
    def zscore_by_industry(
        self,
        factor_df: pd.DataFrame,
        industry_map: Dict[str, str],
        min_samples: int = 10,
    ) -> pd.DataFrame:
        """按行业对因子列做 Z-Score 标准化，并缓存每个行业的统计量。

        具体行为：
        - 输入 `factor_df` 为以股票代码（symbol）为 index、若干因子列为 columns 的 DataFrame。
        - `industry_map` 将 index 中的 symbol 映射到行业编码（或名称）。
          对于没有映射的 symbol，会被分配到特殊行业 "__UNKNOWN__"，以避免在 groupby 时被静默丢弃。
        - 对每个因子列、每个行业组单独计算均值和标准差（只使用非 NaN 值）。
        - 若某行业的有效样本数小于 `min_samples`，则该行业在结果中保持原始值不变，且缓存的该行业统计量的 mean/std 置为 None（同时记录实际样本数 n）。
        - 若某行业的标准差接近 0（< 1e-10），则对该行业所有样本的 z-score 直接置为 0.0（避免除以 0）；同时依然缓存 mean/std。
        - 返回值为与输入相同 index、各因子列被标准化为 z-score 的 DataFrame（dtype=float）。
        - 方法会把本次计算得到的每个因子每个行业的统计量存入 `self._industry_stats`，格式为
            { factor_col: { industry: {"mean": float|None, "std": float|None, "n": int}, ... }, ... }

        该缓存可用于增量标准化（`zscore_incremental`），以对新样本使用之前计算好的行业均值/标准差进行标准化。
        """
        df = factor_df.copy()
        mapped = df.index.map(industry_map)
        # Symbols missing from industry_map become NaN → assign a sentinel group
        # so they are not silently dropped by groupby
        df["_industry"] = [v if pd.notna(v) else "__UNKNOWN__" for v in mapped]

        result = pd.DataFrame(index=df.index, dtype=float)
        self._industry_stats = {}

        factor_cols = [c for c in df.columns if c != "_industry"]
        for col in factor_cols:
            col_stats: Dict[str, Dict] = {}
            z_vals = pd.Series(index=df.index, dtype=float)

            for ind, grp in df.groupby("_industry")[col]:
                valid = grp.dropna()
                n = len(valid)
                if n < min_samples:
                    z_vals.loc[grp.index] = grp
                    col_stats[ind] = {"mean": None, "std": None, "n": n}
                    continue

                mean = valid.mean()
                std = valid.std()
                col_stats[ind] = {"mean": float(mean), "std": float(std), "n": n}

                if std < 1e-10:
                    z_vals.loc[grp.index] = 0.0
                else:
                    z_vals.loc[grp.index] = (grp - mean) / std

            result[col] = z_vals
            self._industry_stats[col] = col_stats

        return result

    def get_industry_stats(self) -> Dict[str, Dict[str, Dict]]:
        """最近一次全量计算的行业均值/标准差。"""
        return self._industry_stats

    # ------------------------------------------------------------------
    # 增量标准化
    # ------------------------------------------------------------------
    @staticmethod
    def zscore_incremental(
        factor_values: Dict[str, Optional[float]],
        industry_code: str,
        stored_stats: Dict[str, Dict[str, Dict]],
    ) -> Dict[str, Optional[float]]:
        """用已存储的行业统计量对单只股票做标准化。"""
        result: Dict[str, Optional[float]] = {}
        for name, raw in factor_values.items():
            if raw is None:
                result[name] = None
                continue
            ind_stats = stored_stats.get(name, {}).get(industry_code)
            if ind_stats is None or ind_stats.get("mean") is None:
                result[name] = raw
                continue
            std = ind_stats["std"]
            if std is None or std < 1e-10:
                result[name] = 0.0
            else:
                result[name] = (raw - ind_stats["mean"]) / std
        return result

    # ------------------------------------------------------------------
    # 市值中性化 (可选)
    # ------------------------------------------------------------------
    @staticmethod
    def market_cap_neutralize(
        factor_series: pd.Series,
        log_market_cap: pd.Series,
    ) -> pd.Series:
        """对 ln(market_cap) 回归取残差。使用 numpy lstsq 避免额外依赖。"""
        valid = factor_series.dropna().index.intersection(log_market_cap.dropna().index)
        if len(valid) < 30:
            return factor_series

        y = factor_series.loc[valid].values
        x = log_market_cap.loc[valid].values
        A = np.column_stack([np.ones_like(x), x])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        residual = y - A @ coef
        return pd.Series(residual, index=valid)

