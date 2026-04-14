from __future__ import annotations

from typing import Any, Dict, List

from artemis.models.workbench import MarketDataQuery
from artemis.services.workbench.providers.base import MarketDataProvider


class PhoenixBarsProvider(MarketDataProvider):
    """Unified PhoenixA bars provider for all asset types and markets.

    Uses the v2 /api/v2/bars/{asset_type}/{market} endpoint via
    PhoenixAClient.get_bars(). Replaces per-asset-type providers.
    """

    name = "phoenix_bars"

    def supports(self, *, asset_type: str, market: str) -> bool:
        # Supports all asset_type/market combinations served by PhoenixA
        return True

    def fetch_bars(self, *, client: Any, query: MarketDataQuery) -> List[Dict[str, Any]]:
        return client.get_bars(
            asset_type=query.asset_type,
            market=query.market,
            symbol=query.symbol,
            start_date=query.start_date,
            end_date=query.end_date,
            period=query.period,
            adjust=query.adjust,
            normalize_for_cache=True,
        )
