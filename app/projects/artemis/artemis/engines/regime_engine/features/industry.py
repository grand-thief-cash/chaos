"""行业集中度特征 — HHI 变体。"""
from __future__ import annotations
from typing import Any, Dict
import numpy as np
import pandas as pd
from artemis.engines.regime_engine.features.base import BaseFeatureComputer

class IndustryFeatureComputer(BaseFeatureComputer):
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        ind_bars: pd.DataFrame = data_bundle.get("industry_bars", pd.DataFrame())
        if ind_bars.empty:
            return {"industry_concentration": 0.0}

        # Expect each row = one industry, column 'return_20d'
        if "return_20d" in ind_bars.columns:
            returns = ind_bars["return_20d"].astype(float).values
        elif "close" in ind_bars.columns:
            returns = np.zeros(1)
        else:
            return {"industry_concentration": 0.0}

        abs_ret = np.abs(returns)
        total = abs_ret.sum()
        if total < 1e-8:
            return {"industry_concentration": 0.0}

        weights = abs_ret / total
        hhi = float((weights ** 2).sum())
        n = len(returns)
        uniform_hhi = 1.0 / max(n, 1)
        conc = max(0.0, min(1.0, (hhi - uniform_hhi) / max(0.3 - uniform_hhi, 1e-8)))
        return {"industry_concentration": conc}

