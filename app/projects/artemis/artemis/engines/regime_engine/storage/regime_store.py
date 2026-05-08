"""Regime 结果读写 — MVP 内存存储。"""

from __future__ import annotations

from typing import Dict, List, Optional

from artemis.engines.regime_engine.models import RegimeFeatures, RegimeState, StrategyAllocation


class RegimeStore:
    """Regime 快照存储 — 接口设计与 PhoenixA API 一致。"""

    def __init__(self) -> None:
        self._results: Dict[str, dict] = {}        # trade_date → dict
        self._features: Dict[str, dict] = {}        # trade_date → dict

    def save_regime_result(
        self,
        state: RegimeState,
        allocation: StrategyAllocation,
        features: Optional[RegimeFeatures] = None,
    ) -> None:
        d = state.to_dict()
        d.update(allocation.to_dict())
        self._results[state.trade_date] = d
        if features is not None:
            self._features[state.trade_date] = features.__dict__

    def get_regime(self, trade_date: str) -> Optional[dict]:
        return self._results.get(trade_date)

    def get_features(self, trade_date: str) -> Optional[dict]:
        return self._features.get(trade_date)

    def get_history(self, limit: int = 60) -> List[dict]:
        dates = sorted(self._results.keys(), reverse=True)[:limit]
        return [self._results[d] for d in dates]

    def list_dates(self) -> List[str]:
        return sorted(self._results.keys())

