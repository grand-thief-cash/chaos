from __future__ import annotations

from typing import Any, Dict, List

from artemis.models.workbench import MarketDataQuery
from artemis.services.workbench.providers.base import MarketDataProvider


class PhoenixIndexZhAProvider(MarketDataProvider):
    """PhoenixA 指数 A 股历史行情 provider。"""

    name = "phoenix_index_zh_a_hist"

    def supports(self, *, asset_type: str, market: str) -> bool:
        return asset_type == "index" and market == "zh_a"

    def fetch_bars(self, *, client: Any, query: MarketDataQuery) -> List[Dict[str, Any]]:
        try:
            return client.get_index_zh_a_hist_bars(
                symbol=query.symbol,
                start_date=query.start_date,
                end_date=query.end_date,
                timeframe=query.period,
                adjust=query.adjust,
            )
        except NotImplementedError as e:
            raise ValueError(
                "unsupported market data provider combination: asset_type=index, market=zh_a (PhoenixA index history endpoint is not implemented yet)"
            ) from e
