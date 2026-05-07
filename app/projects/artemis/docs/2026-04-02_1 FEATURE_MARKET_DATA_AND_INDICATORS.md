# FEATURE: 市场数据与技术指标计算模块

> 日期：2026-04-02（初版），2026-04-03（重设计）
> 状态：设计阶段
> 影响项目：Artemis（后端）、Cthulhu（前端）

---

## 0. 文档目标

本文档描述 Artemis 新增的**市场数据 API** 和**技术指标计算服务**的设计方案。

两个模块各自独立：
- **市场数据 API** — 提供纯 OHLCV K 线数据，供前端绘制蜡烛图
- **指标计算服务** — 基于 pandas-ta 库，按需计算技术指标，供前端叠加到图表上

两者独立于现有的 strategy_engine 和 task_engine，专注服务于策略研发工作台（Workbench）的可视化需求。

> **术语更新（2026-04-13）**：Chaos / Artemis 内部统一使用 `period` 表示周期；`timeframe`、`frequency` 仅允许存在于 PhoenixA / SDK / 外部 API 的适配边界。

---

## 1. 背景与目标

### 1.1 当前问题

Workbench 前端需要绘制 K 线蜡烛图 + 技术指标叠加层，但当前：

1. **没有独立的行情数据 API** — 只有 strategy_engine 内部调 PhoenixA 拉数据，外部无法直接获取 OHLCV
2. **没有技术指标计算能力** — 指标逻辑散落在 backtrader 策略内部，无法单独使用
3. **回测信号无法叠加到 K 线图上** — 前端只拿到了 equity_curve，没有原始价格 + 买卖标记的关联视图

### 1.2 设计目标

1. **独立的行情数据 API** — 纯 OHLCV K 线数据，供前端绘制蜡烛图
2. **独立的指标计算服务** — 基于 pandas-ta，按需计算，返回结构化结果
3. **完全解耦** — K 线图是 K 线图，指标是指标。用户可以只看 K 线不加任何指标
4. **可扩展** — pandas-ta 内置 130+ 指标，新增指标只需注册配置，无需编写计算逻辑
5. **前后端解耦** — 指标在后端计算，前端只负责渲染

### 1.3 明确不做

- 不从零实现指标计算（用 pandas-ta 等成熟库）
- 不引入 ta-lib C 库依赖（编译复杂，跨平台兼容性差）
- 不做实时推送（Phase 1 只做历史数据查询）
- 不在指标服务中包含交易逻辑（纯计算，不产生信号）
- 不替代 strategy_engine 的回测能力

---

## 2. 架构设计

### 2.1 模块关系

```
                      ┌─────────────────────────────┐
                      │        Cthulhu (前端)         │
                      │  K线图(纯蜡烛) + 可选指标叠加   │
                      └──────────┬──────────────────┘
                                 │ HTTP
                ┌────────────────┼──────────────────────┐
                ▼                                       ▼
   GET /workbench/market-data              POST /workbench/indicators
   获取纯 OHLCV K 线数据                    按需计算技术指标
                │                                       │
                ▼                                       ▼
  ┌──────────────────────┐              ┌──────────────────────────┐
  │ market_data_service  │              │   indicator_service      │
  │                      │              │ ┌──────────────────────┐ │
  │ PhoenixAClient       │              │ │ pandas-ta            │ │
  │ (复用已有 client)     │              │ │ (130+ 指标开箱即用)   │ │
  └──────────────────────┘              │ └──────────────────────┘ │
                                        │ ┌──────────────────────┐ │
                                        │ │ indicator_registry   │ │
                                        │ │ (指标注册/参数映射)   │ │
                                        │ └──────────────────────┘ │
                                        └──────────────────────────┘
                                                  ▲
                                          需要 OHLCV 数据
                                                  │
                                  GET /workbench/market-data 复用

独立于:
  - strategy_engine (注册表/构建器/回测)
  - task_engine (任务调度/生命周期)
  - download engine (数据下载/落库)
```

### 2.2 关键设计决策

#### 决策 1：K 线数据与指标计算完全分离

**理由：**
- K 线图是基础展示，很多时候用户只想看蜡烛图 + 成交量
- 指标是可选的分析工具，按需叠加
- 分离后前端可以独立请求 K 线数据，不加载不需要的指标计算开销
- 前端组件更清晰：K 线图组件只管渲染蜡烛，指标叠加层组件只管渲染指标线

#### 决策 2：使用 pandas-ta，不从零实现

**理由：**
- pandas-ta 内置 130+ 指标（SMA、EMA、RSI、MACD、Bollinger、KDJ 等），覆盖绝大多数需求
- 纯 Python，基于 pandas，无 C 依赖，安装简单：`pip install pandas-ta`
- 社区活跃，API 稳定，无需自己维护指标算法正确性
- 性能足够：pandas 向量化计算，750 bars 全量指标 < 10ms
- 我们只需要做一层薄封装，把 pandas-ta 的结果转为 JSON 给前端

#### 决策 3：两个独立 API 端点

**理由：**
- `GET /market-data` — 返回纯 OHLCV，响应快，前端一加载就能画蜡烛图
- `POST /indicators` — 按需计算指标，前端用户选择指标后才调用
- 分离后可以独立缓存、独立优化
- 避免"不传 indicators 时也要走一遍指标引擎判断"的尴尬

---

## 3. API 设计

### 3.1 GET /workbench/market-data

获取纯 K 线 OHLCV 数据。不含任何指标。

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| symbol | string | 是 | - | 股票代码，如 000001 |
| start_date | string | 是 | - | 开始日期 YYYY-MM-DD |
| end_date | string | 是 | - | 结束日期 YYYY-MM-DD |
| period | string | 否 | daily | K 线周期（系统内部唯一标准字段） |
| adjust | string | 否 | nf | 复权方式 |

**Response 200：**

```json
{
  "symbol": "000001",
  "period": "daily",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "bars": [
    {
      "date": "2024-01-02",
      "open": 10.50,
      "high": 10.80,
      "low": 10.40,
      "close": 10.70,
      "volume": 123456789,
      "amount": 1300000000
    }
  ]
}
```

只返回 K 线蜡烛数据，干净纯粹。

### 3.2 POST /workbench/indicators

根据 K 线数据计算技术指标。前端用户选择指标后调用。

**请求体：**

```json
{
  "symbol": "000001",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "period": "daily",
  "adjust": "nf",
  "indicators": [
    {"name": "sma", "params": {"period": 10}},
    {"name": "sma", "params": {"period": 30}},
    {"name": "rsi", "params": {"period": 14}},
    {"name": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}}
  ]
}
```

**Response 200：**

```json
{
  "symbol": "000001",
  "period": "daily",
  "indicators": {
    "sma_10": [null, null, "...", 10.52, 10.55],
    "sma_30": [null, "...", 10.48],
    "rsi_14": [null, "...", 55.3],
    "macd_12_26_9": [...],
    "macd_h_12_26_9": [...],
    "macd_s_12_26_9": [...]
  },
  "indicator_meta": {
    "sma_10": {"type": "line", "color": "#1890ff", "overlay": true},
    "sma_30": {"type": "line", "color": "#faad14", "overlay": true},
    "rsi_14": {"type": "line", "color": "#52c41a", "overlay": false, "y_axis": "rsi"},
    "macd_12_26_9": {"type": "line", "color": "#1890ff", "overlay": false, "y_axis": "macd"},
    "macd_h_12_26_9": {"type": "line", "color": "#faad14", "overlay": false, "y_axis": "macd"},
    "macd_s_12_26_9": {"type": "bar", "color": ["#52c41a", "#ff4d4f"], "overlay": false, "y_axis": "macd"}
  }
}
```

**indicator_meta 说明：**

- `overlay: true` — 叠加到主图（K 线图上），如 SMA、Bollinger
- `overlay: false` — 独立子图，如 RSI、MACD、KDJ
- `y_axis` — 同一子图的指标共享 y 轴名称
- `type` — 渲染类型：`line`（折线）、`bar`（柱状）
- `color` — 推荐颜色，前端可直接使用

后端内部流程：
1. 通过 PhoenixAClient 获取 OHLCV 数据（内部统一使用 `period`，在外部调用边界映射到 PhoenixA 所需字段名）
2. 构建 pandas DataFrame
3. 调用 pandas-ta 计算请求的指标
4. 将结果序列化为 JSON，附带渲染元信息

### 3.3 POST /workbench/run（已有，说明信号叠加方式）

回测结果中已包含 `signals`（买卖信号）和 `equity_curve`，前端在渲染 K 线图时叠加：

```
K 线图（主图，纯蜡烛+成交量）
  ├── 蜡烛图 (bars)
  ├── ▲ 买入信号标记 (signals.BUY)    ← 可选
  └── ▼ 卖出信号标记 (signals.SELL)   ← 可选

指标叠加层（用户按需选择）
  ├── 主图叠加: SMA / EMA / Bollinger  ← 可选，overlay=true
  ├── RSI 子图                         ← 可选，overlay=false
  └── MACD 子图                        ← 可选，overlay=false
```

---

## 4. 指标计算服务设计

### 4.1 目录结构

```
artemis/engines/indicator_engine/
  __init__.py              # 模块入口
  registry.py              # 指标注册表（配置 pandas-ta 的指标映射）
  calculator.py            # 计算入口（调 pandas-ta → 转 JSON）
```

注意：没有 indicators/sma.py 等独立实现文件。所有计算由 pandas-ta 完成。

### 4.2 依赖

```
# requirements.txt 新增
pandas-ta>=0.3.14
```

pandas-ta 基于 pandas/numpy（已安装），无 C 依赖，一行 pip install 即可。

### 4.3 注册表设计

注册表是一份声明式配置，描述每个指标的：
- 对应的 pandas-ta 函数名
- 参数映射（前端参数名 → pandas-ta 参数名）
- 默认参数
- 输出序列映射（pandas-ta 输出列名 → 前端序列名）
- 渲染元信息

```python
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class IndicatorSpec:
    """指标规格定义。"""
    name: str                                    # 指标名，如 "sma"
    display_name: str                            # 显示名，如 "SMA"
    ta_func: str                                 # pandas-ta 函数名，如 "sma"
    params_map: Dict[str, str]                   # 前端参数名 → ta 参数名
    default_params: Dict[str, Any]               # 默认参数
    output_map: Dict[str, Dict[str, Any]]        # ta 输出列名 → {series_name, ...meta}
    overlay: bool                                # 是否叠加到主图
    y_axis: str | None                           # 子图 y 轴名（overlay=false 时有效）


# 示例注册
INDICATOR_REGISTRY: Dict[str, IndicatorSpec] = {
    "sma": IndicatorSpec(
        name="sma",
        display_name="SMA",
        ta_func="sma",
        params_map={"period": "length"},
        default_params={"period": 10},
        output_map={
            "SMA_{length}": {"series_key": "sma_{length}", "type": "line", "color": "#1890ff"},
        },
        overlay=True,
        y_axis=None,
    ),
    "macd": IndicatorSpec(
        name="macd",
        display_name="MACD",
        ta_func="macd",
        params_map={"fast": "fast", "slow": "slow", "signal": "signal"},
        default_params={"fast": 12, "slow": 26, "signal": 9},
        output_map={
            "MACD_{fast}_{slow}_{signal}": {"series_key": "macd_{fast}_{slow}_{signal}", "type": "line", "color": "#1890ff"},
            "MACDh_{fast}_{slow}_{signal}": {"series_key": "macd_h_{fast}_{slow}_{signal}", "type": "bar", "color": ["#52c41a", "#ff4d4f"]},
            "MACDs_{fast}_{slow}_{signal}": {"series_key": "macd_s_{fast}_{slow}_{signal}", "type": "line", "color": "#faad14"},
        },
        overlay=False,
        y_axis="macd",
    ),
    "rsi": IndicatorSpec(
        name="rsi",
        display_name="RSI",
        ta_func="rsi",
        params_map={"period": "length"},
        default_params={"period": 14},
        output_map={
            "RSI_{length}": {"series_key": "rsi_{length}", "type": "line", "color": "#52c41a"},
        },
        overlay=False,
        y_axis="rsi",
    ),
    # ... 其他指标注册同理
}
```

### 4.4 计算入口

```python
import pandas as pd
import pandas_ta as ta
from typing import Any, Dict, List


def compute_indicators(
    df: pd.DataFrame,
    indicator_requests: List[Dict[str, Any]],
) -> tuple[Dict[str, list], Dict[str, Dict[str, Any]]]:
    """
    批量计算指标。

    Args:
        df: OHLCV 数据（至少含 open/high/low/close/volume 列）
        indicator_requests: [{"name": "sma", "params": {"period": 10}}, ...]

    Returns:
        (indicator_series, indicator_meta)
    """
    all_series = {}
    all_meta = {}

    for req in indicator_requests:
        spec = INDICATOR_REGISTRY[req["name"]]
        params = {**spec.default_params, **req.get("params", {})}

        # 映射前端参数名到 pandas-ta 参数名
        ta_params = {}
        for frontend_key, ta_key in spec.params_map.items():
            if frontend_key in params:
                ta_params[ta_key] = params[frontend_key]

        # 调用 pandas-ta
        ta_func = getattr(df.ta, spec.ta_func)
        result_df = ta_func(**ta_params)  # 返回带新列的 DataFrame

        # 提取输出列，转为 JSON
        for ta_col_pattern, col_meta in spec.output_map.items():
            # ta_col_pattern 如 "SMA_{length}"，替换参数值得到实际列名
            actual_col = ta_col_pattern.format(**params)
            if actual_col in result_df.columns:
                series_key = col_meta["series_key"].format(**params)
                values = result_df[actual_col].where(result_df[actual_col].notna(), None).round(4).tolist()
                all_series[series_key] = values
                all_meta[series_key] = {
                    "type": col_meta["type"],
                    "color": col_meta["color"],
                    "overlay": spec.overlay,
                    **({"y_axis": spec.y_axis} if spec.y_axis else {}),
                }

    return all_series, all_meta
```

### 4.5 首批支持的指标

全部由 pandas-ta 提供，无需自己实现：

| 指标 | pandas-ta 函数 | 输出序列 | overlay | 说明 |
|------|---------------|---------|---------|------|
| SMA | `df.ta.sma()` | sma | true | 简单移动平均线 |
| EMA | `df.ta.ema()` | ema | true | 指数移动平均线 |
| RSI | `df.ta.rsi()` | rsi | false | 相对强弱指数 |
| MACD | `df.ta.macd()` | dif, dea, hist | false | 异同移动平均线 |
| Bollinger | `df.ta.bbands()` | upper, mid, lower | true | 布林带 |
| KDJ | `df.ta.stoch()` | k, d | false | 随机指标（Stochastic） |

扩展新指标只需在 `registry.py` 中添加一条 `IndicatorSpec` 配置。

### 4.6 性能基准

pandas-ta 基于 pandas/numpy 向量化操作，3 年日线（~750 bars）：

```
SMA(10,30)    单次 ≈ 0.5ms
RSI(14)       单次 ≈ 2ms
MACD(12,26,9) 单次 ≈ 1ms
全部一起      单次 ≈ 5ms
```

完全满足交互式请求的响应时间要求。

---

## 5. 前端 K 线图设计

### 5.1 组件结构

K 线图组件是**公共组件**，位于 `shared/ui/` 目录，独立于任何 feature，可被任意 feature 引用：

```
shared/ui/
  candlestick-chart/
    candlestick-chart.component.ts    # K 线图主组件（纯蜡烛图 + 成交量）
    candlestick-chart.models.ts       # 组件输入/输出接口定义

features/workbench/ui/
  indicator-selector.component.ts     # 工作台专用的指标选择器 UI
  strategy-config.component.ts        # 策略配置表单（已有）
```

### 5.2 组件设计原则

K 线图作为 `shared/ui` 公共组件：

1. **纯展示组件** — 只接收 bars 数据，绘制蜡烛图 + 成交量
2. **指标是可选输入** — 通过 `@Input indicators` 叠加指标线，不传就是纯蜡烛图
3. **信号是可选输入** — 买卖信号作为可选 `@Input`，回测时才叠加
4. **不关心数据来源** — 不注入 Store 或 Service

```typescript
@Component({
  selector: 'app-candlestick-chart',
  standalone: true,
  imports: [CommonModule, NgxEchartsModule],
})
export class CandlestickChartComponent {
  /** K 线数据（必填） */
  @Input() bars: Bar[] = [];

  /** 成交量数据（可选，默认从 bars 推导） */
  @Input() volume: VolumeBar[] = [];

  /** 指标数据（可选）— key=序列名, value=数值数组 */
  @Input() indicators: Record<string, (number | null)[]> = {};

  /** 指标渲染元信息（可选）— 控制颜色、主图/子图等 */
  @Input() indicatorMeta: Record<string, IndicatorSeriesMeta> = {};

  /** 买卖信号（可选）— 回测时叠加 */
  @Input() signals: SignalEvent[] = [];
}
```

### 5.3 ECharts 图表布局

**默认（无指标）：**

```
┌────────────────────────────────────────────────────┐
│ 主图 (grid 0, 75% 高度)                              │
│                                                      │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│                                                      │
├────────────────────────────────────────────────────┤
│ 成交量 (grid 1, 25% 高度)                             │
│  ▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐     │
└────────────────────────────────────────────────────┘
  ◄────────────── dataZoom ──────────────────────►
```

**叠加指标后：**

```
┌────────────────────────────────────────────────────┐
│ 主图 (grid 0, 60% 高度)                              │
│                                                      │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│  ┃   ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃  ┃     │
│         ──── SMA10 ──── SMA30                        │
│    ▲ BUY                                ▲ BUY        │
│                   ▼ SELL              ▼ SELL         │
│                                                      │
├────────────────────────────────────────────────────┤
│ 成交量 (grid 1, 10% 高度)                             │
│  ▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐     │
├────────────────────────────────────────────────────┤
│ MACD (grid 2, 15% 高度, 用户选择后出现)               │
│   ── DIF  ── DEA  ▐▐ histogram                      │
└────────────────────────────────────────────────────┘
  ◄────────────── dataZoom ──────────────────────►
```

### 5.4 前端数据流

```
1. 页面加载
   → GET /workbench/market-data?symbol=xxx&start_date=...&end_date=...&period=...
   → 拿到纯 bars 数据
   → <app-candlestick-chart [bars]="bars"> 渲染蜡烛图
   （此时没有指标，就是纯 K 线 + 成交量）

2. 用户选择指标（从指标选择器中点选）
   → POST /workbench/indicators
      {symbol, start_date, end_date, period, indicators: [{name: "sma", params: {period: 10}}]}
   → 拿到 indicators + indicator_meta
   → <app-candlestick-chart [bars]="bars" [indicators]="indicators" [indicatorMeta]="meta">
   → 指标线叠加到 K 线图上

3. 运行回测
   → POST /workbench/run
   → 拿到 signals（买卖点）
   → <app-candlestick-chart [signals]="signals" ...>
   → 买卖标记叠加到 K 线上

4. 用户取消指标
   → 清空 indicators 输入
   → 图表恢复为纯蜡烛图
```

### 5.5 指标选择器（workbench feature 专用）

工作台页面新增指标选择区域：

```
┌─ 指标选择 ────────────────────────────────────────┐
│ 主图叠加: [+SMA] [+EMA] [+Bollinger]              │
│ 子图:     [+RSI] [+MACD] [+KDJ]                   │
│                                                    │
│ 已选:                                               │
│   SMA   周期: [10] [30]   [×]                      │
│   MACD  快/慢/信号: [12]/[26]/[9]   [×]            │
└────────────────────────────────────────────────────┘
```

---

## 6. 数据流总览

```
用户操作                         Artemis 后端
────────                         ──────────

1. 输入 symbol + 日期范围
   ──────────────────────────→  GET /workbench/market-data
                                  └── PhoenixAClient.get_strategy_market_bars()
   ←──────────────────────────  返回 {bars} （纯 OHLCV）

2. 前端渲染纯蜡烛图

3. 用户选择指标
   ──────────────────────────→  POST /workbench/indicators
                                  ├── PhoenixAClient.get_strategy_market_bars()
                                  └── pandas-ta 计算指标
   ←──────────────────────────  返回 {indicators, indicator_meta}

4. 前端叠加指标线到 K 线图

5. 运行回测
   ──────────────────────────→  POST /workbench/run
                                  └── strategy_engine (已有)
   ←──────────────────────────  返回 {summary, artifacts.signals}

6. 前端在 K 线图上叠加买卖信号
```

---

## 7. 后端文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `engines/indicator_engine/__init__.py` | **NEW** | 模块入口 |
| `engines/indicator_engine/registry.py` | **NEW** | 指标注册表（pandas-ta 配置映射） |
| `engines/indicator_engine/calculator.py` | **NEW** | 计算入口（调 pandas-ta → 转 JSON） |
| `engines/market_data_service.py` | **NEW** | 行情数据服务（调 PhoenixAClient） |
| `api/http_gateway/workbench_routes.py` | **MODIFY** | 新增 GET /market-data + POST /indicators |
| `models/workbench.py` | **MODIFY** | 新增 market-data / indicators 相关模型 |

注意：不再需要 `indicators/sma.py`、`indicators/ema.py` 等独立实现文件。

---

## 8. 前端文件变更

### 8.1 公共组件（shared/ui/）

| 文件 | 操作 | 说明 |
|------|------|------|
| `shared/ui/candlestick-chart/candlestick-chart.component.ts` | **NEW** | ECharts K 线图组件（纯蜡烛，指标可选叠加） |
| `shared/ui/candlestick-chart/candlestick-chart.models.ts` | **NEW** | 公共类型定义（Bar、IndicatorMeta、SignalEvent 等） |
| `shared/ui/candlestick-chart/index.ts` | **NEW** | Barrel export |

### 8.2 Feature 专用（features/workbench/）

| 文件 | 操作 | 说明 |
|------|------|------|
| `features/workbench/models/workbench.model.ts` | **MODIFY** | 新增 MarketDataResponse、IndicatorsResponse 等接口 |
| `features/workbench/services/workbench-api.service.ts` | **MODIFY** | 新增 getMarketData() + calculateIndicators() 方法 |
| `features/workbench/state/workbench.store.ts` | **MODIFY** | 新增 marketData / indicators signal |
| `features/workbench/ui/indicator-selector.component.ts` | **NEW** | 指标选择器（工作台专用 UI） |
| `features/workbench/ui/backtest-chart.component.ts` | **DELETE** | 被 candlestick-chart + 信号叠加替代 |
| `features/workbench/pages/workbench-research.page.ts` | **MODIFY** | 引用 shared K 线图 + 指标选择器 |

---

## 9. 实施步骤

### Phase 1 — 后端市场数据 API

1. [ ] 创建 `engines/market_data_service.py`（调 PhoenixAClient 获取 OHLCV）
2. [ ] 新增 API 路由 `GET /workbench/market-data`
3. [ ] 验证 API 返回纯 K 线数据

### Phase 2 — 后端指标计算服务

4. [ ] `pip install pandas-ta`
5. [ ] 创建 `engines/indicator_engine/` 目录（3 个文件：__init__.py、registry.py、calculator.py）
6. [ ] 实现 registry.py（IndicatorSpec + 首批 6 个指标配置）
7. [ ] 实现 calculator.py（调 pandas-ta → 转 JSON）
8. [ ] 新增 API 路由 `POST /workbench/indicators`
9. [ ] 验证 API 返回正确的指标数据

### Phase 3 — 前端 K 线图

10. [ ] 创建 `shared/ui/candlestick-chart/` 公共组件（纯蜡烛图 + 成交量）
11. [ ] 定义公共模型（Bar、IndicatorSeriesMeta、SignalEvent）
12. [ ] 实现指标叠加（主图 SMA/EMA/Bollinger + 子图 RSI/MACD/KDJ）
13. [ ] 实现信号标记（买卖点 scatter）
14. [ ] workbench feature 新增 `getMarketData()` + `calculateIndicators()` API 方法
15. [ ] workbench feature 新增指标选择器 UI
16. [ ] workbench-research 页面引用 shared K 线图 + 指标选择器

### Phase 4 — 文档更新

17. [ ] 更新设计文档标注已完成状态
