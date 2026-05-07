"""策略引擎模块，提供策略注册、数据源注册、分析器配置、回测引擎构建和共享执行函数。"""

from artemis.engines.strategy_engine.strategy_registry import strategy_registry
from artemis.engines.strategy_engine.data_providers.registry_map import data_provider_registry
from artemis.engines.strategy_engine.analyzers.registry_map import analyzer_profile_registry
from artemis.engines.strategy_engine.executor import execute_backtest, extract_analyzer_results

__all__ = [
    "strategy_registry",
    "data_provider_registry",
    "analyzer_profile_registry",
    "execute_backtest",
    "extract_analyzer_results",
]

