"""Workbench 市场数据 provider 包。"""

from artemis.services.workbench.providers.base import MarketDataProvider
from artemis.services.workbench.providers.phoenix_stock_hist_provider import PhoenixBarsProvider
from artemis.services.workbench.providers.registry import ProviderRegistry, provider_registry

# Legacy aliases
PhoenixStockZhAProvider = PhoenixBarsProvider
PhoenixIndexZhAProvider = PhoenixBarsProvider

__all__ = [
    "MarketDataProvider",
    "PhoenixBarsProvider",
    "PhoenixStockZhAProvider",
    "PhoenixIndexZhAProvider",
    "ProviderRegistry",
    "provider_registry",
]
