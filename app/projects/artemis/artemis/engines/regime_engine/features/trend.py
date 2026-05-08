"""趋势特征 — distance_from_ma120 & ma20_slope。"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from artemis.engines.regime_engine.features.base import BaseFeatureComputer


class TrendFeatureComputer(BaseFeatureComputer):

    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        index_bars: pd.DataFrame = data_bundle.get("index_bars", {}).get("000300", pd.DataFrame())

        if index_bars.empty or "close" not in index_bars.columns:
            return {"hs300_distance_from_ma120": 0.0, "hs300_ma20_slope": 0.0}

        close = index_bars["close"].astype(float)

        # MA120
        ma120 = close.rolling(120, min_periods=60).mean()
        dist = 0.0
        if len(ma120.dropna()) > 0 and ma120.iloc[-1] and abs(ma120.iloc[-1]) > 1e-8:
            dist = (close.iloc[-1] - ma120.iloc[-1]) / ma120.iloc[-1]

        # MA20 slope (5-day change rate)
        ma20 = close.rolling(20, min_periods=10).mean()
        slope = 0.0
        if len(ma20.dropna()) >= 6 and ma20.iloc[-6] and abs(ma20.iloc[-6]) > 1e-8:
            slope = (ma20.iloc[-1] - ma20.iloc[-6]) / ma20.iloc[-6]

        return {
            "hs300_distance_from_ma120": float(dist),
            "hs300_ma20_slope": float(slope),
        }

