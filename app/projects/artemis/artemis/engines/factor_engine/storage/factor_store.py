"""因子快照读写 — MVP 使用内存存储，后续切换到 PhoenixA。

Phase 4: identity key is security_id (refactor §3.6). symbol is kept only as
a display label (`_security_labels`) stamped from snapshot meta at write time,
so `get_ranking` can decorate rows for symbol-keyed callers (cthulhu) without
reverse-resolving.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


class FactorStore:
    """因子快照存储抽象。

    MVP 阶段使用内存字典，保持接口与 PhoenixA API 一致。
    后续替换为 HTTP 调用 ``POST /api/v2/factor/snapshot`` 等。
    """

    def __init__(self) -> None:
        # {(security_id, market, as_of_date): {raw_factors, norm_factors, meta}}
        self._snapshots: Dict[tuple, dict] = {}
        # {(as_of_date, market): industry_stats_dict}
        self._industry_stats: Dict[tuple, dict] = {}
        # {(as_of_date, market): {security_id -> symbol}} display labels
        self._security_labels: Dict[tuple, Dict[int, str]] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def save_factor_snapshot(
        self,
        as_of_date: str,
        market: str,
        raw_factors: pd.DataFrame,
        normalized_factors: pd.DataFrame,
        snapshot_meta: Optional[Dict[int, dict]] = None,
    ) -> None:
        snapshot_meta = snapshot_meta or {}
        labels = self._security_labels.setdefault((as_of_date, market), {})
        for sec_id in raw_factors.index:
            key = (sec_id, market, as_of_date)
            meta = snapshot_meta.get(sec_id, {"version": "v1.0"})
            self._snapshots[key] = {
                "raw_factors": raw_factors.loc[sec_id].dropna().to_dict(),
                "norm_factors": normalized_factors.loc[sec_id].dropna().to_dict() if sec_id in normalized_factors.index else {},
                "meta": meta,
            }
            symbol = str((meta or {}).get("symbol") or "")
            if symbol:
                labels[sec_id] = symbol

    def save_single_factor(
        self,
        security_id: int,
        as_of_date: str,
        raw_factors: dict,
        norm_factors: dict,
        meta: Optional[dict] = None,
        market: str = "zh_a",
    ) -> None:
        key = (security_id, market, as_of_date)
        meta = meta or {}
        self._snapshots[key] = {
            "raw_factors": {k: v for k, v in raw_factors.items() if v is not None},
            "norm_factors": {k: v for k, v in norm_factors.items() if v is not None},
            "meta": meta,
        }
        symbol = str(meta.get("symbol") or "")
        if symbol:
            labels = self._security_labels.setdefault((as_of_date, market), {})
            labels[security_id] = symbol

    def save_industry_stats(self, as_of_date: str, market: str, stats: dict) -> None:
        self._industry_stats[(as_of_date, market)] = stats

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def load_industry_stats(self, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
        return self._industry_stats.get((as_of_date, market))

    def get_normalized_snapshot(self, as_of_date: str, market: str = "zh_a") -> pd.DataFrame:
        rows = {}
        for (sec_id, mkt, d), snap in self._snapshots.items():
            if d == as_of_date and mkt == market:
                rows[sec_id] = snap.get("norm_factors", {})
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame.from_dict(rows, orient="index")

    def get_security_labels(self, as_of_date: str, market: str = "zh_a") -> Dict[int, str]:
        """security_id -> symbol display labels for the snapshot batch."""
        return dict(self._security_labels.get((as_of_date, market), {}))

    def get_factor_snapshot(self, security_id: int, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
        return self._snapshots.get((security_id, market, as_of_date))

    def list_dates(self, market: str = "zh_a") -> List[str]:
        dates = sorted({d for (_, m, d) in self._snapshots if m == market})
        return dates
