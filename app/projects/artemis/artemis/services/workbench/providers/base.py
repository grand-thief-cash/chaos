from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from artemis.models.workbench import MarketDataQuery


class MarketDataProvider(ABC):
    """Workbench 市场数据 provider 抽象。"""

    name = "unknown"

    @abstractmethod
    def supports(self, *, asset_type: str, market: str) -> bool:
        """判断是否支持指定的 asset_type/market 组合。"""

    @abstractmethod
    def fetch_bars(self, *, client: Any, query: MarketDataQuery) -> List[Dict[str, Any]]:
        """调用上游数据源并返回 OHLCV bars。"""
