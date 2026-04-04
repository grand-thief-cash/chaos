"""交易策略集合，每个策略继承 backtrader.Strategy 并实现 next/notify_order/notify_trade。"""

from artemis.engines.strategy_engine.strategies.sma_cross import SmaCrossStrategy


__all__ = ["SmaCrossStrategy"]

