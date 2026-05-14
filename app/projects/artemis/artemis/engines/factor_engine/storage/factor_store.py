"""因子快照读写 — MVP 使用内存存储，后续切换到 PhoenixA。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


class FactorStore:
    """因子快照存储抽象。

    MVP 阶段使用内存字典，保持接口与 PhoenixA API 一致。
    后续替换为 HTTP 调用 ``POST /api/v2/factor/snapshot`` 等。
    """

    def __init__(self) -> None:
        # {(symbol, market, as_of_date): {raw_factors, norm_factors, meta}}
        self._snapshots: Dict[tuple, dict] = {}
        # {(as_of_date, market): industry_stats_dict}
        self._industry_stats: Dict[tuple, dict] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def save_factor_snapshot(
        self,
        as_of_date: str,
        market: str,
        raw_factors: pd.DataFrame,
        normalized_factors: pd.DataFrame,
        snapshot_meta: Optional[Dict[str, dict]] = None,
    ) -> None:
        snapshot_meta = snapshot_meta or {}
        for sym in raw_factors.index:
            key = (sym, market, as_of_date)
            self._snapshots[key] = {
                "raw_factors": raw_factors.loc[sym].dropna().to_dict(),
                "norm_factors": normalized_factors.loc[sym].dropna().to_dict() if sym in normalized_factors.index else {},
                "meta": snapshot_meta.get(sym, {"version": "v1.0"}),
            }

    def save_single_factor(
        self,
        symbol: str,
        as_of_date: str,
        raw_factors: dict,
        norm_factors: dict,
        meta: Optional[dict] = None,
        market: str = "zh_a",
    ) -> None:
        key = (symbol, market, as_of_date)
        self._snapshots[key] = {
            "raw_factors": {k: v for k, v in raw_factors.items() if v is not None},
            "norm_factors": {k: v for k, v in norm_factors.items() if v is not None},
            "meta": meta or {},
        }

    def save_industry_stats(self, as_of_date: str, market: str, stats: dict) -> None:
        self._industry_stats[(as_of_date, market)] = stats

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def load_industry_stats(self, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
        return self._industry_stats.get((as_of_date, market))

    def get_normalized_snapshot(self, as_of_date: str, market: str = "zh_a") -> pd.DataFrame:
        rows = {}
        for (sym, mkt, d), snap in self._snapshots.items():
            if d == as_of_date and mkt == market:
                rows[sym] = snap.get("norm_factors", {})
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame.from_dict(rows, orient="index")

    def get_factor_snapshot(self, symbol: str, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
        return self._snapshots.get((symbol, market, as_of_date))

    def list_dates(self, market: str = "zh_a") -> List[str]:
        dates = sorted({d for (_, m, d) in self._snapshots if m == market})
        return dates

