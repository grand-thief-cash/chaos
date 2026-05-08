"""Regime 计算 Pipeline 协调器。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from artemis.engines.regime_engine.config import RegimeConfig
from artemis.engines.regime_engine.estimator import RegimeStateEstimator
from artemis.engines.regime_engine.allocator import StrategyAllocator
from artemis.engines.regime_engine.models import RegimeFeatures, RegimeState, StrategyAllocation
from artemis.engines.regime_engine.storage.regime_store import RegimeStore

from artemis.engines.regime_engine.features.trend import TrendFeatureComputer
from artemis.engines.regime_engine.features.breadth import BreadthFeatureComputer
from artemis.engines.regime_engine.features.volatility import VolatilityFeatureComputer
from artemis.engines.regime_engine.features.liquidity import LiquidityFeatureComputer
from artemis.engines.regime_engine.features.style import StyleFeatureComputer
from artemis.engines.regime_engine.features.industry import IndustryFeatureComputer


# ---------------------------------------------------------------------------
# Data provider protocol
# ---------------------------------------------------------------------------

class RegimeDataProvider(Protocol):
    """Regime 数据源协议，MVP 可用 Mock。"""

    def get_index_bars(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]: ...
    def get_market_breadth(self, trade_date: str) -> Dict[str, float]: ...
    def get_industry_daily(self, start_date: str, end_date: str) -> pd.DataFrame: ...
    def get_turnover_stats(self, trade_date: str) -> Dict[str, float]: ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class RegimePipeline:
    """Regime 全流程：数据 → 特征 → 状态估计 → 策略分配 → 存储。"""

    def __init__(
        self,
        data_provider: RegimeDataProvider,
        store: Optional[RegimeStore] = None,
        config: Optional[RegimeConfig] = None,
    ) -> None:
        self.provider = data_provider
        self.store = store or RegimeStore()
        self.config = config or RegimeConfig()

        self.feature_computers = [
            TrendFeatureComputer(),
            BreadthFeatureComputer(),
            VolatilityFeatureComputer(),
            LiquidityFeatureComputer(),
            StyleFeatureComputer(),
            IndustryFeatureComputer(),
        ]
        self.estimator = RegimeStateEstimator(self.config)
        self.allocator = StrategyAllocator()

    def run(self, trade_date: str) -> dict:
        """单日 regime 计算。"""
        data_bundle = self._fetch(trade_date)

        # 计算特征
        features = RegimeFeatures(trade_date=trade_date)
        for computer in self.feature_computers:
            partial = computer.compute(data_bundle)
            for k, v in partial.items():
                if hasattr(features, k):
                    setattr(features, k, v)

        # 状态估计
        state = self.estimator.estimate(features)

        # 策略分配
        allocation = self.allocator.allocate(state)

        # 存储
        self.store.save_regime_result(state, allocation, features)

        result = state.to_dict()
        result.update(allocation.to_dict())
        return result

    def run_backfill(self, trading_dates: List[str]) -> List[dict]:
        """历史回填。"""
        self.estimator.reset()
        results = []
        for d in sorted(trading_dates):
            results.append(self.run(d))
        return results

    def _fetch(self, trade_date: str) -> Dict[str, Any]:
        lookback = self.config.vol_lookback_days
        # 简单回溯日期 (粗略)
        start = str(int(trade_date[:4]) - 2) + trade_date[4:]

        index_bars = self.provider.get_index_bars(
            ["000300", "000016", "399006", "000852", "000015"],
            start, trade_date,
        )
        breadth = self.provider.get_market_breadth(trade_date)
        industry = self.provider.get_industry_daily(start, trade_date)
        turnover = self.provider.get_turnover_stats(trade_date)

        return {
            "index_bars": index_bars,
            "market_breadth": breadth,
            "industry_bars": industry,
            "turnover_stats": turnover,
        }

