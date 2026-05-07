"""策略基类与装饰器注册机制。

BaseRecordingStrategy 统一处理事件采集（equity_curve、signal_events、order_events、
trade_events、position_curve），子类只需实现 on_bar() 专注策略逻辑。

register_strategy 装饰器实现"写策略文件即注册"，自动从 bt.Strategy.params 提取
default_params，消除 registry_map.py 中的重复定义。
"""

from __future__ import annotations

from typing import Any, Dict, List

import backtrader as bt


# ---------------------------------------------------------------------------
# 装饰器收集器：模块加载时收集被 @register_strategy 标记的策略类
# ---------------------------------------------------------------------------

_PENDING_REGISTRATIONS: List[Dict[str, Any]] = []


def register_strategy(
    *,
    code: str,
    supported_modes: tuple[str, ...] = ("historical",),
    supported_timeframes: tuple[str, ...] = ("daily",),
    param_schema: Dict[str, Dict[str, Any]] | None = None,
):
    """策略注册装饰器。

    自动从 bt.Strategy.params 提取 default_params，避免重复定义。

    用法::

        @register_strategy(
            code="sma_cross",
            param_schema={"fast": {"type": "int", "min": 1}, ...},
        )
        class SmaCrossStrategy(BaseRecordingStrategy):
            params = (("fast", 10), ("slow", 30), ("stake", 1))
            ...
    """

    def decorator(cls: type[bt.Strategy]) -> type[bt.Strategy]:
        # 从 bt.Strategy.params 提取默认参数
        # 注意：backtrader 的 MetaClass 会把 params 元组转换为 AutoInfoClass，
        # 因此需要用 _getpairs() 获取，而不是直接遍历元组。
        default_params: Dict[str, Any] = {}
        raw_params = getattr(cls, "params", None)
        if raw_params is not None:
            if hasattr(raw_params, "_getitems"):
                # backtrader AutoInfoClass（类创建后的正常状态）
                default_params = {k: v for k, v in raw_params._getitems() if k not in ("enable_bar_details", "bar_details_level")}
            elif isinstance(raw_params, (tuple, list)):
                # 原始元组（理论上不会走到这里，但作为 fallback）
                for item in raw_params:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        default_params[str(item[0])] = item[1]

        _PENDING_REGISTRATIONS.append(
            {
                "code": code,
                "cls": cls,
                "default_params": default_params,
                "supported_modes": supported_modes,
                "supported_timeframes": supported_timeframes,
                "param_schema": param_schema or {},
            }
        )
        return cls

    return decorator


# ---------------------------------------------------------------------------
# BaseRecordingStrategy：统一事件采集基类
# ---------------------------------------------------------------------------


class BaseRecordingStrategy(bt.Strategy):
    """所有 Artemis 策略的基类，自动采集权益曲线、持仓、订单、交易和信号事件。

    子类只需：
      1. 在 __init__ 中初始化指标（记得调用 super().__init__()）
      2. 实现 on_bar() 方法：策略核心逻辑（买卖判断）
      3. 产生信号时调用 self._record_signal("BUY" / "SELL")

    不需要手动实现 notify_order / notify_trade / equity 记录。
    """

    # 诊断参数声明在基类，所有子类自动继承
    params = (
        ("enable_bar_details", False),
        ("bar_details_level", "trade"),
    )

    def __init__(self):
        super().__init__()
        # 挂单引用：子类在 on_bar 中通过 self.order 判断是否有挂单
        self.order = None

        # 事件采集列表 —— 由基类统一维护
        self.signal_events: List[Dict[str, Any]] = []
        self.order_events: List[Dict[str, Any]] = []
        self.trade_events: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.position_curve: List[Dict[str, Any]] = []

        # 诊断事件列表 —— bar-by-bar 决策记录
        self.bar_detail_events: List[Dict[str, Any]] = []

        # 诊断配置（通过 strategy params 传入）
        self._enable_bar_details: bool = getattr(self.params, "enable_bar_details", False)
        self._bar_details_level: str = getattr(self.params, "bar_details_level", "trade")

    # ── 内部辅助 ─────────────────────────────────────────────

    def _bar_timestamp(self) -> str:
        """获取当前 K 线的时间戳字符串（ISO 格式）。"""
        return bt.num2date(self.datas[0].datetime[0]).isoformat()

    def _record_equity(self) -> None:
        """记录当前 bar 的权益和持仓快照，由基类在 next() 中自动调用。"""
        ts = self._bar_timestamp()
        close_price = float(self.datas[0].close[0])
        self.equity_curve.append(
            {
                "timestamp": ts,
                "close": close_price,
                "cash": float(self.broker.get_cash()),
                "value": float(self.broker.get_value()),
            }
        )
        self.position_curve.append(
            {
                "timestamp": ts,
                "size": float(self.position.size),
                "price": float(self.position.price or 0.0),
            }
        )

    def _record_signal(self, signal: str) -> None:
        """记录买卖信号，子类在产生信号时调用。

        Args:
            signal: 信号类型，通常为 "BUY" 或 "SELL"。
        """
        self.signal_events.append(
            {
                "timestamp": self._bar_timestamp(),
                "signal": signal,
                "close": float(self.datas[0].close[0]),
            }
        )

    def _record_diagnostic(
        self,
        action: str,
        reason: str,
        indicators: Dict[str, Any] | None = None,
    ) -> None:
        """记录一条诊断事件。

        Args:
            action: 动作类型，如 "BUY", "SELL", "HOLD", "SKIP"。
            reason: 决策原因描述。
            indicators: 当前指标快照（可选）。
        """
        if not self._enable_bar_details:
            return
        # bar_details_level == "trade" 时只记录有交易动作的 bar
        if self._bar_details_level == "trade" and action in ("HOLD", "SKIP"):
            return

        ts = self._bar_timestamp()
        close_price = float(self.datas[0].close[0])
        event: Dict[str, Any] = {
            "timestamp": ts,
            "close": close_price,
            "action": action,
            "reason": reason,
            "position_size": float(self.position.size),
            "position_price": float(self.position.price or 0.0),
            "portfolio_value": float(self.broker.get_value()),
            "cash": float(self.broker.get_cash()),
        }
        if indicators:
            event["indicators"] = indicators
        # 计算当前收益
        if self.position.size != 0:
            entry_cost = self.position.price * abs(self.position.size)
            current_value = close_price * abs(self.position.size)
            event["unrealized_pnl"] = round(float(current_value - entry_cost), 2)
            event["unrealized_pnl_pct"] = round(float((current_value - entry_cost) / entry_cost), 6) if entry_cost > 0 else 0.0
        else:
            event["unrealized_pnl"] = 0.0
            event["unrealized_pnl_pct"] = 0.0

        self.bar_detail_events.append(event)

    # ── Backtrader 生命周期钩子 ────────────────────────────────

    def next(self):
        """每根 K 线触发：先记录权益快照，再调用子类的 on_bar()。"""
        self._record_equity()
        self.on_bar()

    def on_bar(self) -> None:
        """子类实现：策略核心逻辑，只关注买卖判断。

        基类已自动处理 equity_curve / position_curve 记录。
        产生信号时调用 self._record_signal("BUY" / "SELL")。
        """
        raise NotImplementedError("子类必须实现 on_bar() 方法")

    def notify_order(self, order: bt.Order) -> None:
        """订单状态变更回调，统一记录订单事件并清理挂单引用。"""
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

        # 记录订单结果到诊断
        if order.status == order.Completed:
            action = "BUY" if order.isbuy() else "SELL"
            self._record_diagnostic(
                f"ORDER_{action}_OK",
                f"订单成交：{action} {abs(order.executed.size):.0f}股 @ {order.executed.price:.4f}，"
                f"金额={abs(order.executed.value):.2f}，手续费={order.executed.comm:.2f}",
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            status_name = order.getstatusname()
            action = "BUY" if order.isbuy() else "SELL"
            reason = "资金不足(Margin)" if order.status == order.Margin else status_name
            self._record_diagnostic(
                "ORDER_FAILED",
                f"订单失败({reason})：{action} {abs(order.size or 0):.0f}股，"
                f"当前现金={self.broker.get_cash():.2f}，持仓={self.position.size:.0f}",
            )

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        """交易平仓回调，统一记录已平仓交易的盈亏明细。"""
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
