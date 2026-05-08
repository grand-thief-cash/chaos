"""流动性特征 — turnover_ratio。"""
from __future__ import annotations
from typing import Any, Dict
from artemis.engines.regime_engine.features.base import BaseFeatureComputer

class LiquidityFeatureComputer(BaseFeatureComputer):
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        stats = data_bundle.get("turnover_stats", {})
        return {
            "turnover_ratio": float(stats.get("turnover_ratio", 1.0)),
        }

