"""数据源集合，每个 provider 定义回测数据的获取配置和字段要求。"""

from artemis.engines.strategy_engine.data_providers.registry_map import (
    DataProviderRegistry,
    DataProviderSpec,
    data_provider_registry,
)

__all__ = ["DataProviderSpec", "DataProviderRegistry", "data_provider_registry"]
