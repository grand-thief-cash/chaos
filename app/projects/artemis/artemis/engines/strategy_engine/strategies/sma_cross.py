from __future__ import annotations

import backtrader as bt

from artemis.engines.strategy_engine.strategies.base import BaseRecordingStrategy, register_strategy


@register_strategy(
    code="sma_cross",
    supported_modes=("historical",),
    supported_timeframes=("daily",),
    param_schema={
        "fast": {"type": "int", "min": 1, "max": 200, "default": 10, "description": "快线周期", "display_name": "Fast Period"},
        "slow": {"type": "int", "min": 1, "max": 500, "default": 30, "description": "慢线周期", "display_name": "Slow Period"},
        "stake": {"type": "int", "min": 1, "default": 1, "description": "每次交易手数", "display_name": "Stake"},
    },
)
class SmaCrossStrategy(BaseRecordingStrategy):
    """SMA 均线交叉策略：快线上穿慢线买入，快线下穿慢线卖出。"""

    params = (
        ("fast", 10),
        ("slow", 30),
        ("stake", 1),
    )

    def __init__(self):
        """初始化策略指标（快慢 SMA、交叉信号）。"""
        super().__init__()
        self.sma_fast = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.fast)
        self.sma_slow = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.slow)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def on_bar(self):
        """每根 K 线触发一次，根据金叉/死叉信号下单。"""
        indicators = {
            "sma_fast": round(float(self.sma_fast[0]), 4),
            "sma_slow": round(float(self.sma_slow[0]), 4),
            "crossover": round(float(self.crossover[0]), 4),
        }

        if self.order:
            self._record_diagnostic("SKIP", "有未完成挂单，等待执行", indicators)
            return

        if not self.position and self.crossover > 0:
            self._record_signal("BUY")
            self.order = self.buy(size=self.params.stake)
            self._record_diagnostic("BUY", f"金叉：快线({indicators['sma_fast']})上穿慢线({indicators['sma_slow']})，无持仓，买入{self.params.stake}手", indicators)
        elif self.position and self.crossover < 0:
            self._record_signal("SELL")
            self.order = self.sell(size=self.position.size)
            self._record_diagnostic("SELL", f"死叉：快线({indicators['sma_fast']})下穿慢线({indicators['sma_slow']})，持仓{self.position.size}手，全部卖出", indicators)
        elif self.position:
            self._record_diagnostic("HOLD", f"持仓中，无交叉信号（crossover={indicators['crossover']}）", indicators)
        else:
            self._record_diagnostic("HOLD", f"空仓，无金叉信号（crossover={indicators['crossover']}）", indicators)
