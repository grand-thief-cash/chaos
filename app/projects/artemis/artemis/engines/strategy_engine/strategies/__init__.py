"""交易策略集合。

新增策略时只需：
  1. 继承 BaseRecordingStrategy
  2. 用 @register_strategy 装饰器声明 code / param_schema
  3. 实现 __init__（初始化指标）和 on_bar（买卖逻辑）
"""

from artemis.engines.strategy_engine.strategies.base import BaseRecordingStrategy, register_strategy
from artemis.engines.strategy_engine.strategies.sma_cross import SmaCrossStrategy


__all__ = ["BaseRecordingStrategy", "register_strategy", "SmaCrossStrategy"]

