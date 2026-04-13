from __future__ import annotations

from typing import Any, Dict, List

from artemis.models.workbench import MarketDataQuery
from artemis.services.workbench.providers.base import MarketDataProvider


class PhoenixStockZhAProvider(MarketDataProvider):
    """PhoenixA 股票 A 股历史行情 provider。"""

    name = "phoenix_stock_zh_a_hist"

    def supports(self, *, asset_type: str, market: str) -> bool:
        return asset_type == "stock" and market == "zh_a"

    def fetch_bars(self, *, client: Any, query: MarketDataQuery) -> List[Dict[str, Any]]:
        return client.get_stock_zh_a_hist_bars(
            symbol=query.symbol,
            start_date=query.start_date,
            end_date=query.end_date,
            timeframe=query.period,
            adjust=query.adjust,
        )
