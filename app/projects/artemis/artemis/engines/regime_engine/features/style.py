"""风格特征 — small_vs_large。"""
from __future__ import annotations
from typing import Any, Dict
import pandas as pd
from artemis.engines.regime_engine.features.base import BaseFeatureComputer

class StyleFeatureComputer(BaseFeatureComputer):
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        idx = data_bundle.get("index_bars", {})
        hs300: pd.DataFrame = idx.get("000300", pd.DataFrame())
        csi1000: pd.DataFrame = idx.get("000852", pd.DataFrame())

        def _return_20d(df: pd.DataFrame) -> float:
            if df.empty or "close" not in df.columns or len(df) < 21:
                return 0.0
            c = df["close"].astype(float)
            return float((c.iloc[-1] / c.iloc[-21]) - 1.0)

        r300 = _return_20d(hs300)
        r1000 = _return_20d(csi1000)
        return {"style_small_vs_large": r1000 - r300}

