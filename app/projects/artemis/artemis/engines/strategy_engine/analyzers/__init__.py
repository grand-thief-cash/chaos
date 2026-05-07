"""分析器配置集合，每个 profile 定义回测中使用的分析器和观察器组合。"""

from artemis.engines.strategy_engine.analyzers.registry_map import (
    AnalyzerProfileRegistry,
    AnalyzerProfileSpec,
    analyzer_profile_registry,
)

__all__ = ["AnalyzerProfileSpec", "AnalyzerProfileRegistry", "analyzer_profile_registry"]
