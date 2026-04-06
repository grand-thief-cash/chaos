from __future__ import annotations

from typing import Any, Dict, List

import backtrader as bt


class SmaCrossStrategy(bt.Strategy):
    """SMA 均线交叉策略：快线上穿慢线买入，快线下穿慢线卖出。"""
    params = (
        ("fast", 10),
        ("slow", 30),
        ("stake", 1),
    )

    def __init__(self):
        """初始化策略指标（快慢 SMA、交叉信号）和事件记录列表。"""
        self.sma_fast = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.fast)
        self.sma_slow = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.slow)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)
        self.order = None
        self.signal_events: List[Dict[str, Any]] = []
        self.order_events: List[Dict[str, Any]] = []
        self.trade_events: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.position_curve: List[Dict[str, Any]] = []

    def _bar_timestamp(self) -> str:
        """获取当前 K 线的时间戳字符串。"""
        return bt.num2date(self.datas[0].datetime[0]).isoformat()

    def next(self):
        """每根 K 线触发一次，执行均线交叉判断和买卖逻辑，并记录权益曲线和持仓曲线。"""
        """每根 K 线触发一次，记录权益曲线并根据金叉/死叉信号下单。"""
        timestamp = self._bar_timestamp()
        close_price = float(self.datas[0].close[0])
        self.equity_curve.append(
            {
                "timestamp": timestamp,
                "close": close_price,
                "cash": float(self.broker.get_cash()),
                "value": float(self.broker.get_value()),
            }
        )
        self.position_curve.append(
            {
                "timestamp": timestamp,
                "size": float(self.position.size),
                "price": float(self.position.price or 0.0),
            }
        )

        if self.order:
            return

        if not self.position and self.crossover > 0:
            self.signal_events.append(
                {
                    "timestamp": timestamp,
                    "signal": "BUY",
                    "close": close_price,
                }
            )
            self.order = self.buy(size=self.params.stake)
        elif self.position and self.crossover < 0:
            self.signal_events.append(
                {
                    "timestamp": timestamp,
                    "signal": "SELL",
                    "close": close_price,
                }
            )
            self.order = self.sell(size=self.position.size)

    def notify_order(self, order: bt.Order):
        """订单状态变更回调，记录订单事件（成交、取消、拒绝等）。"""
        """订单状态变更回调，记录订单事件并清理挂单引用。"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        event = {
            "timestamp": self._bar_timestamp(),
            "status": order.getstatusname(),
            "order_type": "BUY" if order.isbuy() else "SELL",
            "size": float(order.executed.size or order.size or 0.0),
            "price": float(order.executed.price or 0.0),
            "value": float(order.executed.value or 0.0),
            "commission": float(order.executed.comm or 0.0),
        }
        self.order_events.append(event)

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def notify_trade(self, trade: bt.Trade):
        """交易关闭回调，记录已平仓交易的盈亏、持仓时长等信息。"""
        """已平仓交易回调，记录交易统计（盈亏、手续费、持仓周期）。"""
        """交易平仓回调，记录已平仓交易的盈亏明细。"""
        if not trade.isclosed:
            return
        self.trade_events.append(
            {
                "timestamp": self._bar_timestamp(),
                "size": float(trade.size),
                "price": float(trade.price),
                "pnl": float(trade.pnl),
                "pnlcomm": float(trade.pnlcomm),
                "barlen": int(trade.barlen),
            }
        )
