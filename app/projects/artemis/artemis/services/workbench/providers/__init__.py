"""Workbench 市场数据 provider 包。"""

from artemis.services.workbench.providers.base import MarketDataProvider
from artemis.services.workbench.providers.phoenix_index_hist_provider import PhoenixIndexZhAProvider
from artemis.services.workbench.providers.phoenix_stock_hist_provider import PhoenixStockZhAProvider
from artemis.services.workbench.providers.registry import ProviderRegistry, provider_registry

__all__ = [
    "MarketDataProvider",
    "PhoenixStockZhAProvider",
    "PhoenixIndexZhAProvider",
    "ProviderRegistry",
    "provider_registry",
]
