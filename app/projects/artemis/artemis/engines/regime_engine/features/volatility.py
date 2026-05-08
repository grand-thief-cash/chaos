"""波动率特征 — vol_20d & vol_ratio。"""
from __future__ import annotations
import math
from typing import Any, Dict
import numpy as np
import pandas as pd
from artemis.engines.regime_engine.features.base import BaseFeatureComputer

class VolatilityFeatureComputer(BaseFeatureComputer):
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        index_bars: pd.DataFrame = data_bundle.get("index_bars", {}).get("000300", pd.DataFrame())
        if index_bars.empty or "close" not in index_bars.columns or len(index_bars) < 21:
            return {"vol_20d": 0.15, "vol_ratio": 1.0}

        close = index_bars["close"].astype(float)
        ret = close.pct_change().dropna()

        vol_20 = ret.iloc[-20:].std() * math.sqrt(250) if len(ret) >= 20 else 0.15
        vol_60 = ret.iloc[-60:].std() * math.sqrt(250) if len(ret) >= 60 else vol_20

        ratio = vol_20 / vol_60 if vol_60 > 1e-8 else 1.0

        return {
            "vol_20d": float(vol_20),
            "vol_ratio": float(ratio),
        }

