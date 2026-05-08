"""市场广度特征 — breadth_above_ma20_pct。"""
from __future__ import annotations
from typing import Any, Dict
from artemis.engines.regime_engine.features.base import BaseFeatureComputer

class BreadthFeatureComputer(BaseFeatureComputer):
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        breadth = data_bundle.get("market_breadth", {})
        return {
            "breadth_above_ma20_pct": float(breadth.get("above_ma20_pct", 0.5)),
        }

