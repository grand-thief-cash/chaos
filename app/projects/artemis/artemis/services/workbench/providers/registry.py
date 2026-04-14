from __future__ import annotations

from typing import Iterable, List

from artemis.services.workbench.providers.base import MarketDataProvider
from artemis.services.workbench.providers.phoenix_stock_hist_provider import PhoenixBarsProvider


class ProviderRegistry:
    """按 asset_type/market 路由 Workbench 市场数据 provider。"""

    def __init__(self, providers: Iterable[MarketDataProvider] | None = None):
        self._providers: List[MarketDataProvider] = list(providers or [])

    def register(self, provider: MarketDataProvider) -> None:
        self._providers.append(provider)

    def resolve(self, *, asset_type: str, market: str) -> MarketDataProvider:
        for provider in self._providers:
            if provider.supports(asset_type=asset_type, market=market):
                return provider
        raise ValueError(
            f"unsupported market data provider combination: asset_type={asset_type}, market={market}"
        )


provider_registry = ProviderRegistry(
    providers=[
        PhoenixBarsProvider(),
    ]
)
