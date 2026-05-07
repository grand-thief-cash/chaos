# Artemis 策略引擎 — 策略详解文档

> **更新日期**: 2026-04-15
> **版本**: v0.20.0

---

## 目录

1. [架构概览](#1-架构概览)
2. [策略基类 BaseRecordingStrategy](#2-策略基类-baserecordingstrategy)
3. [策略注册机制](#3-策略注册机制)
4. [策略一览](#4-策略一览)
   - 4.1 [SMA 均线交叉策略 (sma_cross)](#41-sma-均线交叉策略-sma_cross)
   - 4.2 [网格交易策略 (grid_trading)](#42-网格交易策略-grid_trading)
5. [回测数据流](#5-回测数据流)
6. [前端集成](#6-前端集成)
7. [如何新增策略](#7-如何新增策略)

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  Workbench / TaskEngine                                     │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  �� 数据获取  │──▶│ execute_     │──▶│ BacktestResult       │ │
│  │ market_   │   │ backtest()   │   │ Normalizer           │ │
│  │ data      │   │ (executor)   │   │ → summary+artifacts  │ │
│  └──────────┘   └──────┬───────┘   └──────────────────────┘ │
│                        │                                     │
│               ┌────────▼────────┐                            │
│               │ Backtrader      │                            │
│               │ Engine Builder  │                            │
│               │ + Strategy      │                            │
│               │ + Analyzers     │                            │
│               └─────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

**核心组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| `BaseRecordingStrategy` | `strategies/base.py` | 策略基类，自动采集 equity_curve、signal_events、order_events、trade_events、position_curve |
| `@register_strategy` | `strategies/base.py` | 装饰器，自动注册策略到全局注册表 |
| `StrategyRegistry` | `strategy_registry.py` | 策略注册表，管理所有可用策略 |
| `execute_backtest()` | `executor.py` | 共享回测执行函数（Workbench/TaskEngine 共用） |
| `BacktestResultNormalizer` | `result_normalizer.py` | 标准化回测结果为统一 JSON 格式 |
| `BacktraderEngineBuilder` | `engine_builder.py` | 构建 Backtrader Cerebro 实例 |

---

## 2. 策略基类 BaseRecordingStrategy

所有策略必须继承 `BaseRecordingStrategy`，它自动处理以下事件采集：

```python
class BaseRecordingStrategy(bt.Strategy):
    """
    自动采集：
      - equity_curve:   每根 K 线的权益快照 {timestamp, close, cash, value}
      - position_curve: 每根 K 线的持仓快照 {timestamp, size, price}
      - signal_events:  买卖信号 {timestamp, signal, close}
      - order_events:   订单状态变更 {timestamp, status, order_type, size, price, value, commission}
      - trade_events:   已平仓交易 {timestamp, size, price, pnl, pnlcomm, barlen}
    """
```

**子类只需实现**：

1. `__init__()` — 初始化指标（记得调用 `super().__init__()`）
2. `on_bar()` — 策略核心逻辑，只关注买卖判断
3. 产生信号时调用 `self._record_signal("BUY")` 或 `self._record_signal("SELL")`

**不需要手动实现**：`next()`、`notify_order()`、`notify_trade()` — 基类已处理。

### 关键属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.order` | `bt.Order | None` | 当前挂单引用，有挂单时为非 None |
| `self.position` | `bt.Position` | 当前持仓，`self.position.size` 获取持仓数量 |
| `self.datas[0]` | `bt.DataBase` | 主数据源，`self.datas[0].close[0]` 获取当前 close |
| `self.broker` | `bt.Broker` | 经纪人实例，`self.broker.get_cash()` / `self.broker.get_value()` |

---

## 3. 策略注册机制

使用 `@register_strategy` 装饰器自动注册，无需手动编辑 `registry_map.py`：

```python
@register_strategy(
    code="my_strategy",                        # 唯一策略代码
    supported_modes=("historical",),           # 支持的模式
    supported_timeframes=("daily", "min5"),    # 支持的时间周期
    param_schema={                             # 参数校验规则
        "fast": {"type": "int", "min": 1, "max": 200, "default": 10},
    },
)
class MyStrategy(BaseRecordingStrategy):
    params = (("fast", 10),)                   # Backtrader 参数定义
    ...
```

**注册流程**：
1. 模块加载时 `@register_strategy` 将策略信息收集到 `_PENDING_REGISTRATIONS`
2. `strategy_registry.py` 中的 `_build_registry()` 读取收集的信息，创建 `StrategySpec`
3. 装饰器注册优先于 `registry_map.py` 中的手动注册

**param_schema 支持的校验规则**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `type` | 参数类型 | `"int"`, `"float"`, `"str"`, `"enum"` |
| `min` | 最小值（int/float） | `1` |
| `max` | 最大值（int/float） | `200` |
| `required` | 是否必填 | `true` |
| `default` | 默认值（供前端表单使用） | `10` |
| `choices` | 可选值列表（str 类型时） | `["arithmetic", "geometric"]` |
| `description` | 参数说明 | `"快线周期"` |
| `display_name` | 前端显示名 | `"Fast Period"` |

---

## 4. 策略一览

### 4.1 SMA 均线交叉策略 (sma_cross)

**文件**：`strategies/sma_cross.py`

**策略原理**：

经典的双均线交叉策略。计算快速和慢速简单移动平均线（SMA），当快线从下方穿越慢线（金叉）时买入，当快线从上方穿越慢线（死叉）时卖出。

```
价格
 │    快线(SMA10)
 │   ╱╲    ╱╲
 │  ╱  ╲  ╱  ╲
 │ ╱    ╲╱    ╲     ← 金叉(BUY): 快线上穿慢线
 │╱   慢线(SMA30)   ← 死叉(SELL): 快线下穿慢线
 └──────────────── 时间
```

**交易逻辑**：

1. **金叉买入**：快线 > 慢线（`crossover > 0`），且当前无持仓 → 买入 `stake` 股
2. **死叉卖出**：快线 < 慢线（`crossover < 0`），且当前有持仓 → 卖出全部持仓

**核心代码**：
```python
def __init__(self):
    super().__init__()
    self.sma_fast = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.fast)
    self.sma_slow = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.slow)
    self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

def on_bar(self):
    if self.order:
        return
    if not self.position and self.crossover > 0:        # 金叉 + 空仓 → 买入
        self._record_signal("BUY")
        self.order = self.buy(size=self.params.stake)
    elif self.position and self.crossover < 0:           # 死叉 + 持��� → 卖出
        self._record_signal("SELL")
        self.order = self.sell(size=self.position.size)
```

**参数**：

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `fast` | int | 10 | 1 ~ 200 | 快线 SMA 周期 |
| `slow` | int | 30 | 1 ~ 500 | 慢线 SMA 周期 |
| `stake` | int | 1 | ≥ 1 | 每次交易手数（买入时固定数量，卖出时清仓） |

**适用场景**：
- ✅ 趋势行情（单边上涨或下跌）
- ❌ 震荡行情（频繁金叉死叉导致亏损）

**支持的时间周期**：`daily`

**注意事项**：
- 由于 SMA 需要历史数据计算，前 `slow` 根 K 线不会产生任何信号
- 卖出时清仓（`self.position.size`），不是固定 `stake` 数量
- 同一时间只有一个方向的持仓（多头或空仓）

---

### 4.2 网格交易策略 (grid_trading)

**文件**：`strategies/grid_trading.py`

**策略原理**：

在固定价格区间 `[lower_price, upper_price]` 内放置多条水平网格线，当价格穿越网格线时触发交易。适用于价格在区间内震荡的行情。

```
价格
 │
15│ ──────── upper_price ────────
 │
13.22│ ─ ─ ─ ─ 网格线4 ─ ─ ─ ─     ← 下穿买入, 上穿卖出
 │
11.66│ ─ ─ ─ ─ 网格线3 ─ ─ ─ ─
 │         ╲ ╱╲  ╱
10.28│ ─ ─ ──╳──╳─ 网格线2 ─ ─     B = 下穿买入
 │       ╱        ╲                S = 上穿卖出
 9.07│ ─ ─ ─ ─ 网格线1 ─ ─ ─ ─
 │
 8│ ──────── lower_price ────────
 └──────────────────────── 时间
```

**交易逻辑**：

1. **放置网格线**：在 `[lower_price, upper_price]` 之间均匀放置 `grid_lines` 条触发线
2. **间距模式**：
   - `arithmetic`（等差）：网格线等价差分布
   - `geometric`（等比）：网格线在 log 空间等差分布（每两条线之间的百分比变动相同）
3. **下穿买入**：价格从上方穿越某条网格线（`prev_close >= level > close`），且该线未持仓 → 买入
4. **上穿卖出**：价格从下方穿越某条网格线（`prev_close <= level < close`），且该线已持仓 → 卖出
5. **每条网格线独立跟踪仓位**：`filled`（已买入持仓）或 `empty`（空仓等待买入）

**核心代码**：
```python
def __init__(self):
    super().__init__()
    upper = self.params.upper_price
    lower = self.params.lower_price
    n_lines = self.params.grid_lines
    mode = self.params.grid_mode
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

    self.grid_filled = [False] * len(self.grid_levels)  # 每条线的仓位状态
    self.prev_close = None

def on_bar(self):
    if self.order:
        return
    close = self.datas[0].close[0]
    if self.prev_close is None:
        self.prev_close = close
        return

    for i, level in enumerate(self.grid_levels):
        if self.prev_close >= level > close and not self.grid_filled[i]:
            self._record_signal("BUY")
            self.order = self.buy(size=self.params.order_size)
            self.grid_filled[i] = True
            break
        if self.prev_close <= level < close and self.grid_filled[i]:
            self._record_signal("SELL")
            self.order = self.sell(size=self.params.order_size)
            self.grid_filled[i] = False
            break

    self.prev_close = close
```

**参数**：

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `upper_price` | float | 15.0 | ≥ 0.01 | 网格上限价格 |
| `lower_price` | float | 8.0 | ≥ 0.01 | 网格下限价格（必须 > 0） |
| `grid_lines` | int | 4 | 1 ~ 50 | 网格线数量（上下限之间的线条数） |
| `order_size` | int | 100 | ≥ 1 | 每格交易股数 |
| `grid_mode` | str | "arithmetic" | `arithmetic` / `geometric` | 网格间距模式 |

**grid_mode 详解**：

| 模式 | 分布方式 | 示例 (8→15, 4条线) | 适用场景 |
|------|----------|---------------------|----------|
| `arithmetic` | 等差分布，固定价差 | 9.4, 10.8, 12.2, 13.6 | 低波动标的 |
| `geometric` | 等比分布，log 等差 | 9.07, 10.28, 11.66, 13.22 | 高波动标的 |

等比模式下每两条网格线之间的价格变动**百分比相同**（约 13.3%），而等差模式下价格**差值相同**（1.4）。

**仓位管理**：
- 每条网格线独立跟踪仓位状态（`grid_filled[i]`）
- 同一网格线上不会重复买入，必须先卖出才能再次触发买入
- **最大同时持仓** = `grid_lines × order_size`（所有网格线都被触发时）
- 每根 K 线最多触发一笔交易（`break` 后等待下一根 K 线）

**适用场景**：
- ✅ 震荡行情（价格在区间内反复波动）
- ✅ 波动率较高的标的（使用 `geometric` 模式）
- ❌ 单边行情（价格突破区间后策略失效）
- ❌ 区间过窄或网格过密（手续费侵蚀利润）

**支持的时间周期**：`daily`, `min5`, `min15`, `min30`, `min60`

**注意事项**：
- `upper_price` 必须大于 `lower_price`
- `lower_price` 必须 > 0（`geometric` 模式需要计算 `log`）
- 网格线不包含上下限本身，只在区间内部放置
- 第一根 K 线不交易（需要 `prev_close` 作为参照）
- 如果初始资金不足以买满所有网格，后续触发可能被 Backtrader 的 margin 机制拒绝

---

## 5. 回测数据流

```
                              ┌─────────────┐
                              │   前端请求    │
                              │ WorkbenchRun │
                              │ Request      │
                              └──────┬───────┘
                                     │
                              ┌──────▼───────┐
                              │ get_market_  │
                              │ bars()       │
                              │ → OHLCV bars │
                              └──────┬───────┘
                                     │
                              ┌──────▼───────┐
                              │ execute_     │
                              │ backtest()   │
                              │ → Backtrader │
                              │   Cerebro    │
                              └──────┬───────┘
                                     │
                      ┌──────────────┼──────────────┐
                      │              │              │
               ┌──────▼──────┐ ┌────▼──────┐ ┌────▼─────────┐
               │ strategy_   │ │ analyzer_ │ │ bars_        │
               │ instance    │ │ results   │ │ processed    │
               │ .equity_    │ │ {returns, │ │ start_cash   │
               │  curve      │ │ drawdown, │ │ end_value    │
               │ .signal_    │ │ sharpe,   │ │              │
               │  events     │ │ trade_    │ │              │
               │ .order_     │ │ analyzer} │ │              │
               │  events     │ │           │ │              │
               │ .trade_     │ │           │ │              │
               │  events     │ │           │ │              │
               │ .position_  │ │           │ │              │
               │  curve      │ │           │ │              │
               └──────┬──────┘ └────┬──────┘ └────┬─────────┘
                      │             │             │
                      └─────────────┼─────────────┘
                                    │
                             ┌──────▼──────────┐
                             │ Normalizer      │
                             │ → summary       │
                             │ → artifacts     │
                             │   + bars (K线)  │
                             └──────┬──────────┘
                                    │
                             ┌──────▼──────────┐
                             │  JSON Response  │
                             │  {run_meta,     │
                             │   summary,      │
                             │   artifacts}    │
                             └─────────────────┘
```

**响应结构**：

```json
{
  "run_meta": {
    "run_id": "wb-1713168000",
    "parent_run_id": null,
    "task_code": "workbench"
  },
  "summary": {
    "strategy_code": "sma_cross",
    "symbol": "000001",
    "period": "daily",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "start_cash": 100000.0,
    "end_value": 105230.5,
    "pnl": 5230.5,
    "pnl_pct": 0.05231,
    "max_drawdown": 3.25,
    "sharpe": 1.23,
    "bars_processed": 242,
    "trade_count": 8,
    "win_count": 5,
    "loss_count": 3,
    "win_rate": 0.625
  },
  "artifacts": {
    "equity_curve": [...],
    "return_curve": [...],
    "signals": [...],
    "trades": [...],
    "orders": [...],
    "positions": [...],
    "bars": [...]
  }
}
```

---

## 6. 前端集成

回测结果在 Cthulhu 前端的 **Workbench Research** 页面展示，包含以下图表组件：

| 组件 | 文件 | 说明 |
|------|------|------|
| `BacktestStatsComponent` | `backtest-stats.component.ts` | 回测统计指标卡片（PnL、收益率、胜率、夏普、最大回撤等） |
| `BacktestKLineChartComponent` | `backtest-kline-chart.component.ts` | **K 线图 + B/S 信号标注**：显示回测期间的蜡烛图，用绿色三角 ▲ + "B" 标注买入点，红色倒三角 ▼ + "S" 标注卖出点 |
| `BacktestChartComponent` | `backtest-chart.component.ts` | 权益曲线（Portfolio Value）+ Buy/Sell 散点图 |
| `ReturnCurveChartComponent` | `return-curve-chart.component.ts` | 收益率曲线，正值绿色、负值红色，带零基线 |

### K 线图 B/S 标注效果

```
  K-Line Chart
  ┌────────────────────────────────────────┐
  │   ╷         ╷                          │
  │   │  B ▲    │                S ▼       │
  │   ┼──┤      ┼──┤     ┌──┐   ┼──┤      │
  │   │  │      │  │     │  │   │  │      │
  │   ╵  │      ╵  │     └──┘   ╵  │      │
  │      ╵         ╵               ╵       │
  ├────────────────────────────────────────┤
  │  ▓▓  ▓▓▓  ▓▓  ▓▓  ▓▓▓▓  ▓▓  ▓▓▓     │ ← Volume
  └────────────────────────────────────────┘
```

- **B（绿色三角 ▲）**：买入信号点，位于 K 线下方
- **S（红色倒三角 ▼）**：卖出信号点，位于 K 线上方
- 支持 DataZoom 缩放和 Cross 十字线 Tooltip

---

## 7. 如何新增策略

**Step 1**: 在 `strategies/` 目录下创建新文件，例如 `my_strategy.py`

```python
from __future__ import annotations
from artemis.engines.strategy_engine.strategies.base import BaseRecordingStrategy, register_strategy

@register_strategy(
    code="my_strategy",
    supported_modes=("historical",),
    supported_timeframes=("daily",),
    param_schema={
        "period": {"type": "int", "min": 1, "max": 100, "default": 20,
                   "description": "指标周期", "display_name": "Period"},
        "threshold": {"type": "float", "min": 0, "default": 0.5,
                      "description": "阈值", "display_name": "Threshold"},
    },
)
class MyStrategy(BaseRecordingStrategy):
    """我的自定义策略。"""
    params = (
        ("period", 20),
        ("threshold", 0.5),
    )

    def __init__(self):
        super().__init__()
        # 初始化指标
        self.indicator = bt.indicators.SomeIndicator(self.datas[0].close, period=self.params.period)

    def on_bar(self):
        if self.order:
            return
        # 买入逻辑
        if not self.position and self.indicator[0] > self.params.threshold:
            self._record_signal("BUY")
            self.order = self.buy(size=100)
        # 卖出逻辑
        elif self.position and self.indicator[0] < -self.params.threshold:
            self._record_signal("SELL")
            self.order = self.sell(size=self.position.size)
```

**Step 2**: 在 `strategies/__init__.py` 中导入

```python
from artemis.engines.strategy_engine.strategies.my_strategy import MyStrategy
__all__ = [..., "MyStrategy"]
```

**Step 3**: 完成！

- 策略会自动注册到 `strategy_registry`
- 前端会自动在策略下拉列表中看到新策略
- `param_schema` 会自动渲染为前端表单
- 无需修改 `registry_map.py`

**Checklist**：

- [ ] 继承 `BaseRecordingStrategy`
- [ ] 使用 `@register_strategy` 装饰器
- [ ] 定义 `params` 元组（Backtrader 参数）
- [ ] `__init__` 中调用 `super().__init__()`
- [ ] 实现 `on_bar()` 方法
- [ ] 产生信号时调用 `self._record_signal("BUY"/"SELL")`
- [ ] 检查 `self.order` 避免重复下单
- [ ] 在 `__init__.py` 中导入
- [ ] 编写单元测试

---

*本文档由 GitHub Copilot 生成，最后更新于 2026-04-15。*

