from __future__ import annotations

import math

from artemis.engines.strategy_engine.strategies.base import BaseRecordingStrategy, register_strategy


@register_strategy(
    code="grid_trading",
    supported_modes=("historical",),
    supported_timeframes=("daily", "min5", "min15", "min30", "min60"),
    param_schema={
        "upper_price": {
            "type": "float",
            "min": 0.01,
            "default": 15.0,
            "description": "网格上限价格",
            "display_name": "Upper Price",
        },
        "lower_price": {
            "type": "float",
            "min": 0.01,
            "default": 8.0,
            "description": "网格下限价格",
            "display_name": "Lower Price",
        },
        "grid_lines": {
            "type": "int",
            "min": 1,
            "max": 50,
            "default": 4,
            "description": "网格线数量（上下限之间的线条数）。每条网格线独立跟踪一个方向的仓位：filled=已在该线买入持仓，empty=空仓等待买入",
            "display_name": "Grid Lines",
        },
        "order_size": {
            "type": "int",
            "min": 1,
            "default": 100,
            "description": "每格交易股数",
            "display_name": "Order Size",
        },
        "grid_mode": {
            "type": "enum",
            "options": ["arithmetic", "geometric"],
            "default": "arithmetic",
            "description": "网格间距模式：arithmetic=等差（固定价差）；geometric=等比（固定百分比/log差值，适合波动率较大的标的）",
            "display_name": "Grid Mode",
        },
    },
)
class GridTradingStrategy(BaseRecordingStrategy):
    """网格交易策略：在固定价格区间内设置网格线，价格下穿买入、上穿卖出。

    工作原理：
      1. 在 [lower_price, upper_price] 之间放置 grid_lines 条网格线
      2. 间距模式：
         - arithmetic（等差）：网格线等价差分布，例如 8→10→12→14
         - geometric（等比）：网格线等百分比分布（log 等差），例如 8→9.52→11.31→13.44
           等比模式下每两条网格线之间的价格变动百分比相同，更适合波动率大的标的
      3. 当价格从上方穿越某条网格线时，买入 order_size 股
      4. 当价格从下方穿越某条网格线时，卖出 order_size 股
      5. 每条网格线独立跟踪仓位状态：filled（已买入持仓）或 empty（空仓）
         同一网格线上不会重复买入，卖出后才能再次触发买入

    参数说明：
      - grid_lines: 网格线数量，即上下限之间有多少条触发线。
        例如 grid_lines=4 会在 [lower, upper] 之间均匀放置 4 条线，
        将区间分为 5 段（grid_lines + 1 个间隔）。
        每条线有独立的仓位状态，所以最大同时持仓 = grid_lines × order_size。

    适用场景：震荡市，价格在一定区间内波动时持续获利。
    """

    params = (
        ("upper_price", 15.0),
        ("lower_price", 8.0),
        ("grid_lines", 4),
        ("order_size", 100),
        ("grid_mode", "arithmetic"),
    )

    def __init__(self):
        super().__init__()

        upper = self.params.upper_price
        lower = self.params.lower_price
        n_lines = self.params.grid_lines
        mode = self.params.grid_mode

        if upper <= lower:
            raise ValueError(f"upper_price ({upper}) must be greater than lower_price ({lower})")
        if n_lines < 1:
            raise ValueError(f"grid_lines ({n_lines}) must be >= 1")
        if lower <= 0:
            raise ValueError(f"lower_price ({lower}) must be > 0 (required for geometric mode)")
        if mode not in ("arithmetic", "geometric"):
            raise ValueError(f"grid_mode must be 'arithmetic' or 'geometric', got '{mode}'")

        # Build grid levels between lower and upper (exclusive of bounds)
        # n_lines 条线将 [lower, upper] 分成 n_lines + 1 个间隔
        n_intervals = n_lines + 1

        if mode == "geometric":
            # 等比网格：在 log 空间中等差分布
            log_lower = math.log(lower)
            log_upper = math.log(upper)
            log_step = (log_upper - log_lower) / n_intervals
            self.grid_levels = [
                round(math.exp(log_lower + log_step * i), 4)
                for i in range(1, n_intervals)
            ]
        else:
            # 等差网格：价格等差分布
            step = (upper - lower) / n_intervals
            self.grid_levels = [
                round(lower + step * i, 4)
                for i in range(1, n_intervals)
            ]

        # Track which grid levels have been "filled" (bought at)
        # True = holding position bought at this level, False = empty
        self.grid_filled = [False] * len(self.grid_levels)

        # Previous close for crossover detection
        self.prev_close = None

        # Pending grid action: only update grid_filled AFTER order completes
        self._pending_grid_idx: int | None = None
        self._pending_action: str | None = None  # "buy" or "sell"

    def notify_order(self, order) -> None:
        """Override to sync grid_filled state with actual order results."""
        # Let base class handle recording first
        super().notify_order(order)

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            # Order finalized — sync grid_filled if it was our grid order
            if self._pending_grid_idx is not None:
                if order.status == order.Completed:
                    # Order succeeded — grid_filled was already tentatively set,
                    # the state is correct, nothing to do.
                    pass
                else:
                    # Order failed — revert the tentative grid_filled change
                    if self._pending_action == "buy":
                        self.grid_filled[self._pending_grid_idx] = False
                    elif self._pending_action == "sell":
                        self.grid_filled[self._pending_grid_idx] = True

                self._pending_grid_idx = None
                self._pending_action = None

    def _grid_indicators(self, close: float) -> dict:
        """构建网格诊断指标快照。"""
        return {
            "close": round(close, 4),
            "prev_close": round(self.prev_close, 4) if self.prev_close is not None else None,
            "grid_levels": self.grid_levels,
            "grid_filled": list(self.grid_filled),
            "total_position": float(self.position.size),
        }

    def on_bar(self):
        if self.order:
            self.prev_close = self.datas[0].close[0]
            self._record_diagnostic("SKIP", "有未完成挂单，等待执行", self._grid_indicators(self.prev_close))
            return

        close = self.datas[0].close[0]

        if self.prev_close is None:
            self.prev_close = close
            self._record_diagnostic("SKIP", "首根K线，初始化前收盘价", self._grid_indicators(close))
            return

        indicators = self._grid_indicators(close)
        acted = False

        for i, level in enumerate(self.grid_levels):
            if self.prev_close >= level > close and not self.grid_filled[i]:
                # 资金检查：预估买入成本，避免因 Margin 被拒
                estimated_cost = close * self.params.order_size
                available_cash = self.broker.get_cash()
                if estimated_cost > available_cash:
                    self._record_diagnostic(
                        "SKIP",
                        f"价格下穿网格线{i+1}（{level}）但资金不足：需要约{estimated_cost:.2f}，可用{available_cash:.2f}",
                        indicators,
                    )
                    acted = True
                    break
                self._record_signal("BUY")
                self.order = self.buy(size=self.params.order_size)
                self.grid_filled[i] = True
                self._pending_grid_idx = i
                self._pending_action = "buy"
                self._record_diagnostic("BUY", f"价格下穿网格线{i+1}（{level}）：{self.prev_close:.4f}→{close:.4f}，买入{self.params.order_size}股", indicators)
                acted = True
                break

            if self.prev_close <= level < close and self.grid_filled[i]:
                self._record_signal("SELL")
                self.order = self.sell(size=self.params.order_size)
                self.grid_filled[i] = False
                self._pending_grid_idx = i
                self._pending_action = "sell"
                self._record_diagnostic("SELL", f"价格上穿网格线{i+1}（{level}）：{self.prev_close:.4f}→{close:.4f}，卖出{self.params.order_size}股", indicators)
                acted = True
                break

        if not acted:
            self._record_diagnostic("HOLD", f"价格{close:.4f}未穿越任何网格线", indicators)

        self.prev_close = close

