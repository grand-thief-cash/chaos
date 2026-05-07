# Artemis 策略引擎架构 Review

> 日期：2026-04-15  
> 范围：`strategy_engine` + `task_engine/backtest` + `indicator_engine` + Workbench 回测链路 + Cthulhu 前端集成  
> 一句话结论：**注册表驱动的白名单架构方向正确、分层清晰，但策略开发体验存在显著摩擦——新增一个策略需要改 3+ 个文件、手动重复录入事件采集代码，Workbench 与 TaskEngine 两条路径存在重复逻辑，需要在持续新增策略之前先补齐基础设施。**

---

## 1. Review 范围

### 1.1 设计文档

| 文档 | 关注点 |
|------|--------|
| `2026-04-01 FEATURE_APPLY_TASK_ORCHESTRATION_IN_BACKTRADING.md` | 回测任务编排总体设计 |
| `2026-04-02_0 FEATURE_STRATEGY_RESEARCH_WORKBENCH.md` | Workbench 交互式回测设计 |
| `2026-04-02_1 FEATURE_MARKET_DATA_AND_INDICATORS.md` | 行情数据与指标引擎设计 |

### 1.2 代码文件

#### strategy_engine 核心

| 文件 | 职责 |
|------|------|
| `strategy_registry.py` | 策略注册表 + `StrategySpec` 定义 |
| `strategies/registry_map.py` | 策略注册映射（手动维护） |
| `strategies/sma_cross.py` | SMA 均线交叉策略实现 |
| `engine_builder.py` | Backtrader Cerebro 装配 |
| `result_normalizer.py` | 回测结果标准化 → summary + artifacts |
| `data_providers/registry_map.py` | 数据源注册表 |
| `analyzers/registry_map.py` | 分析器配置注册表 |

#### task_engine 回测集成

| 文件 | 职责 |
|------|------|
| `task_engine/backtest/campaign.py` | `BacktraderCampaignTask` 编排父任务 |
| `task_engine/backtest/run.py` | `BacktraderRunTask` 单次回测执行 |
| `task_engine/base.py` | 基类生命周期 |
| `task_engine/orchestrator_unit.py` | Orchestrator 基类 |

#### Workbench 回测路径

| 文件 | 职责 |
|------|------|
| `services/workbench/backtest.py` | 轻量交互式回测服务 |
| `services/workbench/market_data.py` | 市场数据获取 + 缓存 |
| `api/http_gateway/workbench_routes.py` | Workbench API 路由 |
| `models/workbench.py` | 请求/响应模型 |

#### indicator_engine

| 文件 | 职责 |
|------|------|
| `indicator_engine/registry.py` | 声明式指标注册表（SMA/EMA/RSI/MACD/Bollinger/KDJ 等） |
| `indicator_engine/calculator.py` | 指标批量计算入口 |

#### 测试

| 文件 | 覆盖 |
|------|------|
| `tests/test_backtrader_phase1.py` | Campaign 编排 + Run 执行 + 结果持久化 |
| `tests/test_workbench_phase1_contract.py` | Workbench 维度归一化 + 回测接口契约 |

---

## 2. 做得好的地方

### 2.1 注册表驱动的白名单架构

`strategy_code → Strategy class`、`data_provider_code → DataProviderSpec`、`analyzer_profile → AnalyzerProfileSpec` 三层注册表设计是正确的。它有效收口了 Backtrader 的开放性，避免了"任意 class path 动态加载"带来的安全和一致性风险。任务入参只传 code + params，不传可执行对象。

### 2.2 strategy_engine 与 task_engine 的清晰分离

`strategy_engine` 作为独立模块，不依赖 `TaskContext` 或 `TaskEngine`。这使得 Workbench 能直接调用 `strategy_engine` 而不经过 task 生命周期，形成了两条路径的清晰分工：

- **TaskEngine 路径**：重生命周期、编排、落库、进度上报
- **Workbench 路径**：轻量级、直接返回 JSON、快速迭代

### 2.3 结果标准化设计

`BacktestResultNormalizer` 将 Backtrader 原始对象统一转为 `summary + artifacts` 两层结构，禁止 PhoenixA 直接消费原始对象。`plot_manifest` + `plot_series` 的预留为前端渲染提供了稳定数据接口。

### 2.4 indicator_engine 声明式注册

指标注册表通过 `IndicatorSpec` 将计算函数、默认参数、渲染元信息（`overlay`、`y_axis`、`series_meta`）绑定在一起，前端可以通过 `/workbench/indicators` 动态获取可用指标列表和渲染规则，实现了前后端指标面板的解耦。

### 2.5 任务编排复用

`BacktraderCampaignTask` 复用了已有的 `OrchestratorUnit` 编排模式，Campaign = N 只股票 × M 组参数，子任务串行执行、进度上报、fail-fast 全部继承基类行为，没有重造调度系统。

### 2.6 测试覆盖

Phase 1 核心场景有单测覆盖：Campaign 编排 + 子任务执行 + 结果持久化 + 失败链路 + Workbench 契约。Mock 设计干净，`FakePhoenixABacktestClient` 模拟了完整的 PhoenixA 交互。

### 2.7 文档跟踪

设计文档（`2026-04-01` 回测编排、`2026-04-02_0` Workbench、`2026-04-02_1` 行情指标）形成了完整的决策链条，Phase 1 checklist 详细到文件级别，后续维护者可以追溯设计意图。

---

## 3. 关键问题清单

### P0：架构层面的摩擦与重复

---

#### P0-1：新增策略的开发摩擦过大

**现象**

新增一个策略至少需要改动 3 个文件：

1. 编写策略类（如 `strategies/sma_cross.py`）
2. 在 `strategies/registry_map.py` 中添加 `StrategyRegistration` 条目
3. 在策略类内手动实现 5 个事件列表（`signal_events`、`order_events`、`trade_events`、`equity_curve`、`position_curve`）及其 `notify_order`、`notify_trade` 回调

每个策略都必须重复实现的代码约 60 行（`__init__` 中的列表初始化 + `_bar_timestamp` + `next` 中的 equity/position 记录 + `notify_order` + `notify_trade`），这些代码与策略自身逻辑完全无关。

**影响**

- 开发新策略的时间成本中，**>50% 花在复制粘贴样板代码**
- 遗漏任一事件记录字段，前端展示缺数据（如缺 `position_curve` 导致持仓图无法渲染）
- 不同策略之间事件记录格式可能不一致（手动维护无约束）
- 不利于快速迭代：开发者应该只关心策略逻辑（`next` 中的买卖判断），而不是基础设施

**建议**

创建 `BaseRecordingStrategy(bt.Strategy)` 基类，将事件采集逻辑统一下沉：

```python
class BaseRecordingStrategy(bt.Strategy):
    """所有 Artemis 策略的基类，自动采集事件数据。"""

    def __init__(self):
        super().__init__()
        self.signal_events = []
        self.order_events = []
        self.trade_events = []
        self.equity_curve = []
        self.position_curve = []

    def _bar_timestamp(self) -> str:
        return bt.num2date(self.datas[0].datetime[0]).isoformat()

    def _record_equity(self):
        """在每根 K 线结束时记录权益和持仓，由基类自动调用。"""
        ts = self._bar_timestamp()
        self.equity_curve.append({
            "timestamp": ts,
            "close": float(self.datas[0].close[0]),
            "cash": float(self.broker.get_cash()),
            "value": float(self.broker.get_value()),
        })
        self.position_curve.append({
            "timestamp": ts,
            "size": float(self.position.size),
            "price": float(self.position.price or 0.0),
        })

    def _record_signal(self, signal: str):
        """记录买卖信号，由子类在产生信号时调用。"""
        self.signal_events.append({
            "timestamp": self._bar_timestamp(),
            "signal": signal,
            "close": float(self.datas[0].close[0]),
        })

    def next(self):
        self._record_equity()
        self.on_bar()

    def on_bar(self):
        """子类实现：策略核心逻辑，只关注买卖判断。"""
        raise NotImplementedError

    def notify_order(self, order):
        # ... 统一实现，子类不需要重写
        pass

    def notify_trade(self, trade):
        # ... 统一实现，子类不需要重写
        pass
```

这样 `SmaCrossStrategy` 可以简化为：

```python
class SmaCrossStrategy(BaseRecordingStrategy):
    params = (("fast", 10), ("slow", 30), ("stake", 1))

    def __init__(self):
        super().__init__()
        self.sma_fast = bt.indicators.SMA(self.datas[0].close, period=self.params.fast)
        self.sma_slow = bt.indicators.SMA(self.datas[0].close, period=self.params.slow)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def on_bar(self):
        if self.order:
            return
        if not self.position and self.crossover > 0:
            self._record_signal("BUY")
            self.order = self.buy(size=self.params.stake)
        elif self.position and self.crossover < 0:
            self._record_signal("SELL")
            self.order = self.sell(size=self.position.size)
```

**效果**：新增策略从 ~110 行降至 ~20 行，只写策略逻辑。

---

#### P0-2：策略注册过程繁琐，缺少自动发现机制

**现象**

当前注册流程为：

1. 写策略类
2. 手动在 `strategies/registry_map.py` 中添加 `StrategyRegistration` 条目
3. `strategy_registry.py` 在模块加载时遍历 `STRATEGY_REGISTRY_MAP` 注册

虽然设计文档说"Phase 1 手动维护"，但随着策略数量增长，`registry_map.py` 会变成一个不断膨胀的大文件，且容易出现 import 和参数不一致。

**影响**

- 新增策略的人容易忘记同步更新 registry_map
- 策略的 `default_params` 在策略类的 `params` 和 `StrategyRegistration.default_params` 中重复定义，可能不一致
- 所有策略的 import 集中在一个文件，模块加载变慢

**建议**

引入装饰器注册机制，让策略类自描述：

```python
@register_strategy(
    code="sma_cross",
    supported_modes=("historical",),
    supported_timeframes=("daily",),
    param_schema={"fast": {"type": "int", "min": 1}, ...},
)
class SmaCrossStrategy(BaseRecordingStrategy):
    params = (("fast", 10), ("slow", 30), ("stake", 1))
    ...
```

装饰器自动从 `params` 提取 `default_params`，消除重复定义。配合 `strategies/` 目录下的自动扫描（或显式 `__init__.py` import），实现"添加策略文件即注册"。

---

#### P0-3：Workbench 与 TaskEngine 路径存在重复逻辑

**现象**

以下逻辑在两条路径中重复实现：

| 逻辑 | `services/workbench/backtest.py` | `task_engine/backtest/run.py` |
|------|------|------|
| `_extract_analyzer_results` | ✅ 独立实现 | ✅ 独立实现（代码完全相同） |
| 策略校验 → 引擎构建 → 执行 → 标准化 | ✅ 完整流程 | ✅ 完整流程 |
| 参数合并 `{**default_params, **user_params}` | ✅ 第 87 行 | ✅ 第 123 行 |
| 结果调用 `BacktestResultNormalizer.normalize(...)` | ✅ 相同参数列表 | ✅ 相同参数列表 |

**影响**

- 修改结果规范化逻辑需要同步改两处
- Bug 修复容易遗漏一条路径
- 后续新增策略类型时需要在两处都测试

**建议**

提取一个与 TaskContext 无关的核心执行函数，两条路径共用：

```python
# strategy_engine/executor.py
def execute_backtest(
    *,
    df: pd.DataFrame,
    strategy_spec: StrategySpec,
    strategy_params: dict,
    analyzer_profile: AnalyzerProfileSpec,
    cash: float,
    commission: float,
) -> dict:
    """执行一次回测，返回原始结果（strategy_instance, analyzer_results, ...）"""
    cerebro = BacktraderEngineBuilder.build(...)
    start_cash = float(cerebro.broker.get_cash())
    strategies = cerebro.run()
    strategy_instance = strategies[0]
    analyzer_results = extract_analyzer_results(strategy_instance)
    end_value = float(cerebro.broker.get_value())
    bars_processed = len(df.index)
    return {
        "strategy_instance": strategy_instance,
        "analyzer_results": analyzer_results,
        "bars_processed": bars_processed,
        "start_cash": start_cash,
        "end_value": end_value,
    }
```

- `services/workbench/backtest.py` → 调用 `execute_backtest()` + `normalize()`
- `task_engine/backtest/run.py` → 调用 `execute_backtest()` + `normalize()` + `sink()`

---

### P1：能力缺口

---

#### P1-1：`param_schema` 校验能力过于基础

**现象**

当前 `StrategySpec.validate_params()` 只支持：

- `required` 检查
- `type == "int"` 类型校验
- `min` 最小值约束

不支持：`float`、`str`、`enum`、`range`（min + max）、`default` 回填、`description` 描述。

**影响**

- 前端无法渲染 `float` 类型的参数输入框（如止损比例 `stop_loss_pct`）
- 前端无法渲染下拉选择（如均线类型 `ma_type: ["SMA", "EMA", "WMA"]`）
- 无法给用户展示参数含义
- 随着策略复杂度增加，校验能力不足会导致运行时错误

**建议**

扩展 `param_schema` 格式，支持前端表单动态渲染所需的完整类型：

```python
param_schema = {
    "fast": {
        "type": "int",
        "min": 1,
        "max": 200,
        "default": 10,
        "description": "快线周期",
        "display_name": "Fast Period",
    },
    "stop_loss_pct": {
        "type": "float",
        "min": 0.01,
        "max": 0.5,
        "default": 0.05,
        "description": "止损比例",
    },
    "ma_type": {
        "type": "enum",
        "options": ["SMA", "EMA", "WMA"],
        "default": "SMA",
        "description": "均线类型",
    },
}
```

同步更新 `validate_params()` 以支持新增类型。

---

#### P1-2：`DataProviderSpec` 停留在 Stub 阶段

**现象**

设计文档（Section 3.3.2）描述了 `data_provider_code` 应该承载的完整职责：

- 参数校验（`validate`）
- 数据读取与标准化（`load_history`）
- Backtrader feed 构建（`build_bt_feed`）
- Warmup 数据预装（`load_warmup`）
- 诊断信息输出（`snapshot_diagnostics`）

但当前 `DataProviderSpec` 只是一个数据结构，不包含任何行为方法。实际的数据获取逻辑散落在 `BacktraderRunTask.execute()` 和 `services/workbench/market_data.py` 中。

**影响**

- 如果后续需要支持非 PhoenixA 数据源（如本地 CSV、第三方 API），无法通过注册表扩展
- 数据获取、清洗、转换逻辑与任务执行逻辑耦合
- 与设计文档的意图不一致，可能导致后续开发者困惑

**建议**

Phase 2 之前可以不改，但需要在接口上做预留。给 `DataProviderSpec` 增加一个可选的 `adapter_cls` 字段，后续实现时让 adapter 承载数据获取逻辑。短期内可以先维持"Spec 只是元数据"的状态，但不要把数据获取逻辑继续扩散到更多地方。

---

#### P1-3：`AnalyzerProfileSpec` 扩展性不足

**现象**

`AnalyzerProfileSpec` 中 `analyzers` 和 `observers` 的类型是 `Tuple[Tuple[str, type, dict], ...]`，使用元组硬编码。设计文档提到的 `recorders`、`summary_mapping`、`plot_capabilities` 均未实现。

当前只有一个 profile `default_hist_v1`，无法根据策略特性动态调整分析器组合。

**影响**

- 所有策略使用完全相同的分析器组合，无法为特定策略添加专用分析器
- 无法在不修改代码的情况下创建新 profile
- Recorder 层缺失，事件采集逻辑被迫写在策略类内部（见 P0-1）

**建议**

短期保持现状，但在实现 `BaseRecordingStrategy`（P0-1）后，recorder 的职责自然由基类承担。`AnalyzerProfileSpec` 的 recorder 字段可以推迟到 Phase 2 实现。

---

#### P1-4：`plot_manifest` 硬编码且过于简单

**现象**

`result_normalizer.py` 中 `plot_manifest` 是硬编码的：

```python
"plot_manifest": {
    "version": "v1",
    "charts": [{
        "chart_code": "equity_overview",
        "series": ["equity_curve", "signals"],
        "x_axis": "timestamp",
    }],
}
```

所有策略返回完全相同的 plot_manifest，不包含：

- 策略自身的指标线（如 SMA 快线/慢线）
- 买卖标记的样式
- 子图配置（如 MACD 柱状图）
- 与 `indicator_engine` 的联动

**影响**

- 前端无法根据策略类型渲染不同的图表布局
- 前端必须硬编码来猜测哪些 series 应该叠加在主图、哪些应该放子图
- `indicator_engine` 已经有完善的 `series_meta`（overlay、y_axis、color），但 `plot_manifest` 没有利用

**建议**

让策略通过基类声明自己的 plot 需求：

```python
class SmaCrossStrategy(BaseRecordingStrategy):
    plot_config = {
        "overlays": ["sma_fast", "sma_slow"],   # 叠加到主图的序列
        "markers": ["signals"],                  # 买卖标记
        "sub_charts": [],                        # 子图
    }
```

`result_normalizer.py` 在标准化时读取策略的 `plot_config`，生成更丰富的 `plot_manifest`。

---

#### P1-5：缺少策略版本管理

**现象**

当前 `StrategySpec` 没有 `version` 字段。如果策略逻辑修改（如调整信号生成条件），历史回测结果与当前策略版本无法对应。

**影响**

- 无法区分同一策略不同版本的回测结果
- 策略逻辑 Bug 修复后，无法追溯哪些历史结果受影响
- 不利于策略迭代审计

**建议**

在 `StrategySpec` / `StrategyRegistration` 中增加 `version` 字段，并在 `run_summary` 中持久化。可以先用简单的字符串版本号（如 `"v1"`、`"v1.1"`），不需要复杂的版本管理系统。

---

### P2：增强机会

---

#### P2-1：缺少策略对比 / 基准比较能力

**现象**

当前系统只能独立运行单个策略，没有：

- 多策略对比回测（同一数据、不同策略）
- 与基准（如沪深 300）的对比
- `parameter_grid` 结果的聚合对比视图

**影响**

- 研发人员无法快速对比不同策略/参数的优劣
- 前端需要自行实现对比逻辑

**建议**

Phase 2 考虑添加：

1. Workbench 侧支持 `POST /workbench/compare`，接受多组策略+参数，返回并列结果
2. `BacktraderCampaignTask` 的 `finalize` 阶段生成参数网格对比 summary
3. 前端增加 comparison view 页面

---

#### P2-2：缺少参数优化 / 网格搜索结果聚合

**现象**

`parameter_grid` 功能在 Campaign 层展开为多个子任务，但子任务结果各自独立落库。没有机制对网格搜索结果做聚合排序（如按 Sharpe 降序排列所有参数组合）。

**建议**

在 Campaign `finalize` 或 Workbench 侧增加 grid result aggregation：

```json
{
  "grid_summary": [
    {"params": {"fast": 5, "slow": 20}, "sharpe": 1.2, "pnl_pct": 0.15},
    {"params": {"fast": 10, "slow": 30}, "sharpe": 0.9, "pnl_pct": 0.08}
  ],
  "best_params": {"fast": 5, "slow": 20}
}
```

---

#### P2-3：缺少 WebSocket / SSE 实时进度推送

**现象**

Workbench 回测是同步 HTTP 请求，回测耗时较长时前端只能等待。Campaign 子任务进度通过 Cronjob 回调上报，前端无法实时感知。

**建议**

Phase 2 考虑 WebSocket 或 SSE 推送：

- Workbench 长耗时回测启动后返回 `job_id`，前端通过 WebSocket 订阅进度
- Campaign 进度推送到 Cthulhu，不仅依赖 Cronjob 回调

---

#### P2-4：策略与指标引擎缺少联动

**现象**

`indicator_engine` 和 `strategy_engine` 是两个完全独立的模块。策略（如 SMA Cross）在内部使用 Backtrader 的指标，而 `indicator_engine` 使用 `ta` 库独立计算。两套指标体系不互通。

**影响**

- 前端展示策略使用的指标需要额外请求 `/workbench/indicators`
- 策略内部的指标值（如 SMA 快线慢线）不包含在回测结果中
- 同一个 SMA 被两套系统分别计算，逻辑可能不一致

**建议**

在 `BaseRecordingStrategy` 中增加 `indicator_series` 记录，策略可以声明自己使用了哪些指标，运行时自动记录指标值到 artifacts。前端可以直接从回测结果中获取指标数据而不需要二次请求。

---

#### P2-5：前端集成的具体缺口

**现象**

从 Cthulhu ARCHITECTURE.md 和 workbench_routes 来看，前端侧还缺少：

- 回测结果详情页（需要消费 summary + artifacts）
- 策略对比视图
- 网格搜索结果展示
- 回测历史列表（需要 PhoenixA query API）

**建议**

前端实现路线建议：

1. **Phase 1**：策略选择 + 参数表单 + 单次回测 + 权益曲线 + 统计卡片（基本完成）
2. **Phase 2**：回测历史列表 + 策略对比 + 网格结果表格 + 指标叠加
3. **Phase 3**：实时模拟进度 + WebSocket + 高级图表（K 线 + 买卖标记 + 指标子图）

---

## 4. 最需要先做的三件事

### ① 创建 `BaseRecordingStrategy` 基类

**收益**：将新增策略的代码量从 ~110 行降至 ~20 行，消除事件采集的样板代码。  
**改动范围**：新增 `strategy_engine/strategies/base.py`，改造 `sma_cross.py`。  
**验收标准**：`SmaCrossStrategy` 只保留 `__init__` 和 `on_bar`，所有测试通过。

### ② 提取共享回测执行函数，消除 Workbench / TaskEngine 路径重复

**收益**：Bug 修复和逻辑变更只需改一处，降低维护成本。  
**改动范围**：新增 `strategy_engine/executor.py`，重构 `services/workbench/backtest.py` 和 `task_engine/backtest/run.py`。  
**验收标准**：两条路径共用核心执行逻辑，`_extract_analyzer_results` 只有一份实现。

### ③ 扩展 `param_schema` 支持前端表单渲染

**收益**：前端可以根据 schema 动态渲染参数表单，支持 float/enum/range/description。  
**改动范围**：修改 `StrategySpec.validate_params()`，更新 `strategies/registry_map.py` 中的 schema 定义。  
**验收标准**：`GET /workbench/strategies` 返回的 schema 可以直接驱动 Ant Design 表单生成。

---

## 5. 改进路线图

### Phase 1（立即执行 · 预计 2-3 天）

| 序号 | 改动 | 涉及文件 | 优先级 |
|------|------|---------|--------|
| 1 | 创建 `BaseRecordingStrategy` | 新增 `strategies/base.py`，改 `sma_cross.py` | P0 |
| 2 | 提取共享执行函数 `execute_backtest()` | 新增 `executor.py`，改 `backtest.py`(workbench)，改 `run.py`(task) | P0 |
| 3 | 消除 `_extract_analyzer_results` 重复 | 移入 `executor.py` 或 `engine_builder.py` | P0 |
| 4 | 扩展 `param_schema` | 改 `strategy_registry.py`，改 `strategies/registry_map.py` | P1 |

### Phase 2（策略能力增强 · 预计 1 周）

| 序号 | 改动 | 涉及模块 |
|------|------|---------|
| 5 | 装饰器注册机制 + 策略自动发现 | `strategy_registry.py`，`strategies/` |
| 6 | 策略版本管理 | `StrategySpec`，`StrategyRegistration`，`result_normalizer.py` |
| 7 | 丰富 `plot_manifest`（策略感知） | `BaseRecordingStrategy`，`result_normalizer.py` |
| 8 | 策略模板生成器 / 脚手架 CLI | 新增 `scripts/new_strategy.py` |
| 9 | 策略对比 API | `services/workbench/`，`workbench_routes.py` |

### Phase 3（高级功能 · 按需）

| 序号 | 改动 | 涉及模块 |
|------|------|---------|
| 10 | 网格搜索结果聚合 | `campaign.py` finalize，新增聚合 API |
| 11 | WebSocket / SSE 实时进度 | Artemis + Cthulhu |
| 12 | 策略-指标引擎联动 | `BaseRecordingStrategy`，`indicator_engine` |
| 13 | `DataProviderSpec` adapter 化 | `data_providers/` |
| 14 | 多策略对比前端页面 | Cthulhu `features/backtest/` |

---

## 6. 策略开发快速上手指南（目标态）

完成 Phase 1 改进后，新增一个策略的理想流程应该是：

```
1. 在 strategies/ 下创建新文件（如 rsi_reversal.py）
2. 继承 BaseRecordingStrategy
3. 用装饰器声明 code / param_schema
4. 实现 __init__（初始化指标）和 on_bar（买卖逻辑）
5. 完成 ✓ —— 注册、事件采集、前端表单、图表渲染全部自动化
```

**示例**：

```python
# strategies/rsi_reversal.py
from artemis.engines.strategy_engine.strategies.base import BaseRecordingStrategy, register_strategy

@register_strategy(
    code="rsi_reversal",
    supported_modes=("historical",),
    supported_timeframes=("daily",),
    param_schema={
        "rsi_period": {"type": "int", "min": 2, "max": 100, "default": 14, "description": "RSI 周期"},
        "oversold": {"type": "int", "min": 1, "max": 50, "default": 30, "description": "超卖阈值"},
        "overbought": {"type": "int", "min": 50, "max": 99, "default": 70, "description": "超买阈值"},
        "stake": {"type": "int", "min": 1, "default": 1, "description": "每次交易手数"},
    },
)
class RsiReversalStrategy(BaseRecordingStrategy):
    params = (("rsi_period", 14), ("oversold", 30), ("overbought", 70), ("stake", 1))

    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(self.datas[0].close, period=self.params.rsi_period)

    def on_bar(self):
        if self.order:
            return
        if not self.position and self.rsi < self.params.oversold:
            self._record_signal("BUY")
            self.order = self.buy(size=self.params.stake)
        elif self.position and self.rsi > self.params.overbought:
            self._record_signal("SELL")
            self.order = self.sell(size=self.position.size)
```

**对比当前**：

| 维度 | 当前 | 改进后 |
|------|------|--------|
| 新增文件数 | 1 策略文件 + 1 registry_map 修改 | 1 策略文件 |
| 策略文件行数 | ~110 行 | ~25 行 |
| 需要手动实现 | 事件列表初始化、时间戳函数、equity 记录、notify_order、notify_trade | 仅 `__init__` + `on_bar` |
| 遗漏风险 | 高（手动复制粘贴） | 低（基类统一处理） |
| 前端表单适配 | 需确认 param_schema 格式 | 装饰器中声明，自动可用 |

---

## 7. 已完成的改进（2026-04-15）

以下 P0 / P1 改进已在本次 review 中同步完成：

### ✅ P0-1：创建 `BaseRecordingStrategy` 基类

- 新增 `strategies/base.py`，统一处理 equity_curve / position_curve / signal_events / order_events / trade_events 的采集
- 子类只需实现 `__init__`（初始化指标）和 `on_bar()`（买卖逻辑）
- `SmaCrossStrategy` 从 111 行精简到 46 行（含装饰器元数据），纯策略逻辑仅 ~20 行

### ✅ P0-2：装饰器注册机制 `@register_strategy`

- 新增 `strategies/base.py` 中的 `register_strategy` 装饰器
- 自动从 backtrader `params` 提取 `default_params`（通过 `_getpairs()` 兼容 backtrader MetaClass）
- `strategy_registry.py` 同时兼容装饰器和 `registry_map.py` 两种注册方式（向后兼容）
- `SmaCrossStrategy` 已迁移到装饰器注册

### ✅ P0-3：提取共享回测执行函数 `execute_backtest()`

- 新增 `strategy_engine/executor.py`，包含：
  - `extract_analyzer_results()` — 唯一实现，消除了两处重复
  - `execute_backtest()` — 引擎构建 → 执行 → 提取结果的完整流程
- `services/workbench/backtest.py` 已重构为调用 `execute_backtest()`
- `task_engine/backtest/run.py` 已重构为调用 `execute_backtest()`

### ✅ P1-1：增强 `param_schema` 校验

- `StrategySpec.validate_params()` 新增支持：
  - `float` 类型 + min/max 范围
  - `str` 类型
  - `enum` 类型 + options 校验
  - `max` 最大值约束（int / float）
  - `default`、`description`、`display_name` 元数据字段（前端表单渲染用）
- `StrategySpec` 新增 `version` 字段（默认 `"v1"`）

### ✅ 测试修复

- 修复 `test_backtrader_phase1.py` 中 `timeframe` → `period` 的命名不一致
- 修复 `test_workbench_phase1_contract.py` 中 monkeypatch 路径适配新的 `execute_backtest` 函数
- 修复 `test_workbench_phase1_contract.py::test_get_market_bars_uses_period_internally_and_maps_to_phoenix_timeframe`：
  - **问题**：UT 设计问题，`FakePhoenixClient` 实现了旧的 `get_stock_zh_a_hist_bars()` 方法，但生产代码已在 v0.17.0 迁移到 `PhoenixBarsProvider → client.get_bars()` 路径
  - **修复**：`FakePhoenixClient` 改为实现 `get_bars()` 方法，断言从 `fake_client.calls[0]["timeframe"]` 改为 `fake_client.calls[0]["period"]`（v2 接口统一使用 `period`）

### 变更文件清单

| 文件 | 操作 |
|------|------|
| `strategies/base.py` | 新增：BaseRecordingStrategy + @register_strategy |
| `strategy_engine/executor.py` | 新增：execute_backtest + extract_analyzer_results |
| `strategies/sma_cross.py` | 重构：继承 BaseRecordingStrategy，使用 @register_strategy |
| `strategy_registry.py` | 重构：增强 validate_params，支持装饰器注册 |
| `services/workbench/backtest.py` | 重构：使用 execute_backtest()，移除重复代码 |
| `task_engine/backtest/run.py` | 重构：使用 execute_backtest()，移除重复代码 |
| `strategies/__init__.py` | 更新：导出 BaseRecordingStrategy、register_strategy |
| `strategy_engine/__init__.py` | 更新：导出 execute_backtest、extract_analyzer_results |
| `tests/test_backtrader_phase1.py` | 修复：timeframe → period |
| `tests/test_workbench_phase1_contract.py` | 修复：monkeypatch 适配 executor |

---

## 8. 最终结论

**策略引擎的架构方向正确、分层清晰**——注册表白名单、summary + artifacts 两层结果、strategy_engine 与 task_engine 分离、indicator_engine 声明式注册，这些设计决策都是对的。

**核心问题不是架构有多糟糕，而是策略开发的 DX（Developer Experience）还不够好。** 本次已完成 P0 级改进（BaseRecordingStrategy + 装饰器注册 + 共享执行函数 + param_schema 增强），新增策略的代码量从 ~110 行降至 ~25 行，Workbench 和 TaskEngine 路径已消除重复逻辑。

后续按 Phase 2/3 路线图推进即可：策略版本管理 → 丰富 plot_manifest → 策略对比 API → 网格搜索聚合 → WebSocket 实时进度。

