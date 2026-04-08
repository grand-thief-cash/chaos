# Artemis 下载引擎（download_engine）设计方案

> **状态：PENDING** — Phase 1（目录重组）已完成。Phase 2+ 设计存在根本性缺陷需重新设计，具体问题见下方 §14。

## 0. 文档目标

本文档基于当前 Artemis 已存在的任务编排骨架与 `strategy_engine` 注册表模式，在**尽量不引入过度设计**的前提下，给出一个适用于多源异构数据下载的引擎方案。

目标覆盖：

1. **解决下载任务爆炸**：当前 `task_units/download/zh/` 下已有 4 个任务类，随着市场（HK/US）、品种（基金/ETF/期货/债券）增加，文件数量会组合式增长。
2. **收敛共性逻辑**：参数转换、schema 标准化、下游 sink 等逻辑散落在各任务中，应抽入统一引擎。
3. **引入 `engines/` 顶层文件夹**：统一收纳所有引擎（`strategy_engine`、`download_engine`、`task_engine`），明确各引擎的职责边界。
4. **重命名 `task_units` → `task_engine`**：`task_units` 本质是任务引擎（对应 `core/task_engine.py` 的编排实现），应归入 `engines/`。
5. **重命名 `bt_engine` → `backtest`**：`bt_engine` 不是一个独立的引擎，而是 task_engine 下的一个任务入口（portal），与 `download` 对称命名更清晰。
6. **增量设计**：不迁移现有下载任务代码，新任务走引擎，老任务保持不动。

> 本文档当前只做设计，不修改代码。

---

## 1. 需求理解与边界

### 1.1 这次要解决的问题

当前 `task_units/download/` 的组织方式：

```text
task_units/download/
└── zh/
    ├── stock_zh_a_hist_parent.py       # OrchestratorUnit
    ├── stock_zh_a_hist_child.py        # WorkerUnit
    ├── stock_zh_a_list.py              # WorkerUnit
    ├── stock_zh_a_market_category.py   # WorkerUnit
    ├── utils.py                        # 参数转换
    └── __init__.py
```

问题在于：

- **维度爆炸**：市场（zh/hk/us）× 品种（stock/fund/etf/index/bond）× 数据类型（hist/realtime/minute），组合导致文件数暴涨。
- **共性散落**：每个任务类各自实现参数转换（如 `utils.convert_to_baostock_params`）、schema 标准化（如 `stock_zh_a_hist_child.post_process` 中硬编码字段列表）、下游 sink（各自 `ctx.dept_http.get(PhoenixA)`）。
- **无法复用**：新增一个"港股历史数据下载"任务，需要重写一套 Parent/Child，虽然逻辑与 A 股几乎一样。

### 1.2 本次设计的目标

- 引入 `download_engine` 模块，提供注册表驱动的下载能力。
- 引入 `engines/` 顶层文件夹，统一收纳所有引擎。
- 搭建框架代码（注册表、适配器接口），不迁移现有任务。
- 新增下载任务只需：注册数据源 + 注册 schema + 注册 sink，无需编写新的 TaskUnit 类。

### 1.3 本文档不负责的范围

- 不迁移现有 `task_units/download/zh/` 下的代码；
- 不修改 `TaskCode` 枚举、`TaskRegistry`、`BaseTaskUnit` 等现有骨架；
- 不修改 `PhoenixAClient`；
- 不做分布式下载调度、断点续传、流式下载等高级能力；
- 目录重组（`task_units` → `engines/task_engine`、`bt_engine` → `backtest`）的具体执行步骤在本文档范围，但会控制影响面。

---

## 2. 当前代码基础与痛点

### 2.1 现有下载任务共性分析

| 共性 | 当前散落位置 | 举例 |
|---|---|---|
| 数据源参数转换 | `utils.py` | `convert_to_baostock_params("frequency", period)` |
| 数据获取 | 各 WorkerUnit 的 `execute()` | `bs.query_history_k_data_plus(...)`、`requests.get(url)` |
| Schema 标准化 | 各 WorkerUnit 的 `post_process()` | 硬编码 `expected_cols`、`float_cols`、`int_cols` |
| 下游写入 | 各 WorkerUnit 的 `sink()` | `phoenix_client.upsert_stock_zh_a_hist(...)` |
| 父子编排 | 各 OrchestratorUnit 的 `plan()` | 查询代码列表 → 拆分为子任务 |

### 2.2 即将面临的维度增长

```text
市场维度：CN_A → + HK → + US → + JP → ...
品种维度：stock → + fund → + etf → + index → + bond → + futures
数据类型：hist_daily → + hist_weekly → + hist_minute → + realtime → + fundamentals
数据源：  baostock → + akshare → + mairui → + tushare → + custom API
```

如果不做引擎化，每个组合都可能需要一个新的 TaskUnit 文件。

### 2.3 已有可复用的模式：strategy_engine

`strategy_engine` 已经验证了注册表模式在 Artemis 中的可行性：

- `StrategySpec` + `StrategyRegistry`：策略注册与查询；
- `DataProviderSpec` + `DataProviderRegistry`：数据源注册；
- `AnalyzerProfileSpec` + `AnalyzerProfileRegistry`：分析器配置注册；
- `BacktraderEngineBuilder`：统一构建引擎；
- `BacktestResultNormalizer`：统一标准化结果。

`bt_engine`（Campaign/Run）通过 registry 查询 spec，不直接依赖具体实现类。这一模式可以直接复用到下载场景。

### 2.4 现有目录组织的问题

当前 Artemis 顶层结构：

```text
artemis/
├── strategy_engine/      # 引擎，平铺
├── task_units/           # 任务编排，平铺
│   ├── bt_engine/        # 回测任务入口
│   └── download/         # 下载任务入口
├── core/
│   ├── clients/          # HTTP 客户端（PhoenixA、Cronjob）
│   ├── sdk/              # SDK 封装（baostock、amazing_data）
│   ├── task_engine.py    # TaskEngine 核心
│   └── task_registry.py  # TaskRegistry
├── api/
├── consts/
...
```

问题：

- `strategy_engine` 和 `task_units` 本质都是引擎，但平铺在不同位置，命名不统一；
- `bt_engine` 名字暗示它是一个独立引擎，实际上它只是 task_engine 下的一个任务入口（portal），与 `download` 不对称；
- `core/sdk/` 下的 baostock、amazing_data SDK 只被下载任务使用，放在 core 层不够精确；
- `core/clients/` 下的 PhoenixA、Cronjob 客户端被多个引擎共用，属于共享基础设施。

---

## 3. 总体设计原则

### 3.1 原则一：引擎与编排分离，统一归入 engines/

所有引擎统一归入 `engines/` 文件夹，`task_units` 重命名为 `task_engine` 后也归入：

```text
engines/
  ├── task_engine/          # 任务编排引擎（原 task_units）
  │   ├── backtest/         # 回测任务入口（原 bt_engine）
  │   └── download/         # 下载任务入口
  ├── strategy_engine/      # 策略引擎
  └── download_engine/      # 下载引擎（新增）

core/                       # 共享基础设施（不变）
  ├── clients/              # HTTP 客户端（PhoenixA、Cronjob）
  ├── sdk/                  # SDK 框架 + 具体 SDK 实现（全部留在 core）
  ├── task_engine.py
  └── task_registry.py
```

**依赖方向**：

```text
engines/task_engine/backtest  →  engines/strategy_engine   （回测调用策略）
engines/task_engine/download  →  engines/download_engine   （下载调用下载引擎）
engines/download_engine       →  core/clients              （下载引擎用 PhoenixA 客户端）
engines/task_engine           →  core/clients              （任务引擎用 Cronjob 客户端）
```

**单向依赖**：`task_engine → 其他 engines → core`，engines 不依赖 task_engine。

### 3.2 原则二：注册表模式收口扩展性

新增下载能力 = 注册新条目，不写新 TaskUnit：

```text
新增"港股 ETF 历史数据下载"：
  1. source_registry.register(baostock_hk_etf_spec)
  2. schema_registry.register(etf_hist_schema)
  3. sink_registry.register(phoenixa_etf_hist_sink)
  → 无需新增任何 TaskUnit 类
```

### 3.3 原则三：统一管线 fetch → normalize → sink

所有下载任务共享同一条管线：

```text
fetch(params) → DataFrame → normalize(schema) → DataFrame → sink(meta, DataFrame)
```

各阶段由注册表条目驱动，不硬编码。

### 3.4 原则四：增量设计，不迁移现有代码

- 现有 `task_units/download/zh/` 下所有任务保持不变；
- `download_engine` 作为增量框架搭建；
- 新下载任务走引擎，老任务在合适时机迁移；
- 不影响当前运行中的 cronjob 任务。

---

## 4. 目录结构变更

### 4.1 当前结构 → 建议结构

**当前**：

```text
artemis/
├── strategy_engine/              # 策略引擎，平铺
│   ├── strategy_registry.py
│   ├── data_providers/
│   ├── analyzers/
│   ├── strategies/
│   ├── engine_builder.py
│   └── result_normalizer.py
├── task_units/                   # 任务编排，平铺
│   ├── base.py
│   ├── orchestrator_unit.py
│   ├── worker_unit.py
│   ├── bt_engine/               # 回测任务入口
│   │   ├── campaign.py
│   │   └── run.py
│   └── download/                # 下载任务入口
│       └── zh/
├── core/
│   ├── clients/                  # HTTP 客户端
│   │   ├── dept_clients.py       # 基础 HTTP 客户端
│   │   ├── phoenixA_client.py    # PhoenixA 客户端
│   │   └── cronjob_client.py     # Cronjob 客户端
│   ├── sdk/                      # SDK 封装
│   │   ├── base.py               # BaseSDK, StatefulSDK, StatelessSDK
│   │   ├── manager.py            # SDKManager 单例
│   │   ├── baostock_sdk.py       # Baostock SDK
│   │   └── amazing_data_sdk.py   # AmazingData SDK
│   ├── task_engine.py
│   ├── task_registry.py
│   ├── config_manager.py
│   ├── context.py
│   └── runtime_files.py
├── api/
├── consts/
├── models/
├── log/
└── utils/
```

**建议**：

```text
artemis/
├── engines/                      # 新增：统一引擎层
│   ├── __init__.py
│   ├── task_engine/              # 任务编排引擎（原 task_units）
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── orchestrator_unit.py
│   │   ├── worker_unit.py
│   │   ├── backtest/            # 回测任务入口（原 bt_engine）
│   │   │   ├── __init__.py
│   │   │   ├── campaign.py
│   │   │   └── run.py
│   │   └── download/            # 下载任务入口
│   │       └── zh/
│   ├── strategy_engine/          # 策略引擎（原 artemis/strategy_engine）
│   │   ├── strategy_registry.py
│   │   ├── data_providers/
│   │   ├── analyzers/
│   │   ├── strategies/
│   │   ├── engine_builder.py
│   │   └── result_normalizer.py
│   └── download_engine/          # 下载引擎（新增）
│       ├── __init__.py
│       ├── source_registry.py
│       ├── schema_registry.py
│       ├── sink_registry.py
│       ├── pipeline.py
│       └── sources/
│           ├── __init__.py
│           ├── baostock_source.py    # 含原 core/sdk/baostock_sdk.py 的 SDK 封装
│           ├── akshare_source.py     # 含原 core/sdk/amazing_data_sdk.py 的 SDK 封装
│           └── mairui_source.py
├── core/                         # 共享基础设施（不变）
│   ├── clients/                  # HTTP 客户端（被多个引擎共用）
│   │   ├── dept_clients.py
│   │   ├── phoenixA_client.py
│   │   └── cronjob_client.py
│   ├── sdk/                      # SDK 封装（被多个引擎共用）
│   │   ├── base.py               # BaseSDK, StatefulSDK, StatelessSDK
│   │   ├── manager.py            # SDKManager
│   │   ├── baostock_sdk.py       # Baostock SDK（download/backtest 均可能使用）
│   │   └── amazing_data_sdk.py   # AmazingData SDK（download/backtest 均可能使用）
│   ├── task_engine.py
│   ├── task_registry.py
│   ├── config_manager.py
│   ├── context.py
│   └── runtime_files.py
├── api/
├── consts/
├── models/
├── log/
└── utils/
```

### 4.2 变更汇总

| 变更项 | 原路径 | 新路径 | 说明 |
|---|---|---|---|
| 新增 engines 层 | — | `engines/` | 统一收纳所有引擎 |
| task_units 重命名 | `task_units/` | `engines/task_engine/` | 本质是任务引擎 |
| bt_engine 重命名 | `task_units/bt_engine/` | `engines/task_engine/backtest/` | 与 download 对称 |
| strategy_engine 迁移 | `strategy_engine/` | `engines/strategy_engine/` | 归入引擎层 |
| download_engine 新增 | — | `engines/download_engine/` | 下载能力引擎 |

### 4.3 `engines/` 各层定位

| 层 | 职责 | 不负责 |
|---|---|---|
| `engines/task_engine/` | 任务编排（参数校验、子任务规划、进度上报、生命周期） | 不内嵌数据获取/转换的具体实现 |
| `engines/strategy_engine/` | 策略注册、数据源注册、分析器配置、引擎构建 | 不感知任务调度 |
| `engines/download_engine/` | 数据源适配、schema 标准化、下游 sink、下载管线 | 不感知任务调度 |
| `core/` | 共享基础设施（HTTP 客户端、SDK 框架、配置、上下文） | 不包含业务逻辑 |

### 4.4 core/sdk 和 core/clients 不变

SDK 和 clients 是共享基础设施，被多个引擎共用，全部保留在 `core/`：

| 组件 | 使用方 | 结论 |
|---|---|---|
| `PhoenixAClient` | backtest（读行情、写结果）、download（写数据）、strategy_engine（读数据） | 共用 → 留在 core |
| `CronjobClient` | task_engine（进度上报、finalize） | 共用 → 留在 core |
| `dept_clients.py` | 所有客户端的基类 | 共用 → 留在 core |
| `baostock_sdk.py` | 当前仅 download，但 backtest 未来也可能需要直接拉取数据 | 共用 → 留在 core |
| `amazing_data_sdk.py` | 当前仅 download，但其他引擎也可能使用 | 共用 → 留在 core |
| `base.py` / `manager.py` | SDK 框架 | 共用 → 留在 core |

**原则**：SDK 和 clients 按职责分层，不按当前使用方归类。即使某个 SDK 目前只有一个引擎在用，它仍然是基础设施层的一部分。

`download_engine/sources/` 中的适配器通过 `sdk_mgr.get_sdk()` 引用 `core/sdk/` 下的公共 SDK，不自行封装。

---

## 5. download_engine 详细设计

### 5.1 目录结构

```text
artemis/engines/download_engine/
├── __init__.py               # 导出注册表单例
├── source_registry.py        # 数据源注册表
├── schema_registry.py        # 输出 schema 注册表
├── sink_registry.py          # 下游 sink 注册表
├── pipeline.py               # 统一管线
└── sources/
    ├── __init__.py           # 导出 source 注册表填充后的单例
    ├── baostock_source.py    # Baostock 适配器（引用 core/sdk/baostock_sdk.py）
    ├── akshare_source.py     # Akshare 适配器（引用 core/sdk/amazing_data_sdk.py）
    └── mairui_source.py      # Mairui API 适配器
```

数据源适配器引用 `core/sdk/` 下的公共 SDK 封装，不自行实现 SDK 管理。SDK 和 clients 是共享基础设施，download、backtest 等引擎均可能使用，因此统一留在 `core/`。

### 5.2 三层注册表

对标 `strategy_engine` 的三层注册（strategy / data_provider / analyzer_profile），download_engine 也有三层：

| 注册表 | 职责 | 对标 |
|---|---|---|
| `source_registry` | 数据源：从哪里获取数据、如何调用 API | `strategy_registry` |
| `schema_registry` | 输出格式：数据有哪些字段、如何标准化 | `data_provider_registry` |
| `sink_registry` | 下游写入：写到哪个服务、调用哪个 API | `analyzer_profile_registry` |

### 5.3 统一管线（DownloadPipeline）

```text
                    ┌──────────────────┐
  params ──────────►│  source.fetch()  │
                    └────────┬─────────┘
                             │ DataFrame (原始)
                    ┌────────▼─────────┐
                    │ schema.normalize()│
                    └────────┬─────────┘
                             │ DataFrame (标准化)
                    ┌────────▼─────────┐
                    │   sink.write()   │
                    └────────┬─────────┘
                             │ bool (成功/失败)
```

管线不依赖 task lifecycle，可在任何上下文中使用（TaskUnit、脚本、测试）。

---

## 6. 注册表设计

### 6.1 DataSourceSpec + DataSourceRegistry

#### DataSourceSpec

```python
@dataclass(frozen=True)
class DataSourceSpec:
    """数据源规格，定义数据来源、支持的市场和数据类型。"""
    code: str                              # 唯一标识，如 "baostock_hist"
    adapter_cls: Type[DataSourceAdapter]   # 适配器类
    supported_markets: tuple[str, ...]     # 支持的市场，如 ("CN_A",)
    supported_data_types: tuple[str, ...]  # 支持的数据类型，如 ("stock_hist_daily", "stock_hist_weekly")
    config_schema: Dict[str, Any]          # 参数校验规则（可选）
```

#### DataSourceAdapter（抽象基类）

```python
from abc import ABC, abstractmethod

class DataSourceAdapter(ABC):
    """数据源适配器基类，所有数据源必须实现此接口。"""

    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> List[str]:
        """校验参数，返回错误信息列表。"""
        ...

    @abstractmethod
    def fetch(self, ctx: TaskContext, params: Dict[str, Any]) -> pd.DataFrame:
        """执行数据获取，返回原始 DataFrame。"""
        ...

    def before_fetch(self, ctx: TaskContext, params: Dict[str, Any]) -> None:
        """可选：获取前的准备工作（如 SDK 登录）。"""
        pass

    def after_fetch(self, ctx: TaskContext, params: Dict[str, Any]) -> None:
        """可选：获取后的清理工作（如 SDK 登出）。"""
        pass
```

#### DataSourceRegistry

```python
class DataSourceRegistry:
    """数据源注册表，管理所有可用的数据源。"""
    def __init__(self) -> None:
        self._registry: Dict[str, DataSourceSpec] = {}

    def register(self, spec: DataSourceSpec) -> None: ...
    def get(self, code: str) -> DataSourceSpec | None: ...
    def require(self, code: str) -> DataSourceSpec: ...
    def has(self, code: str) -> bool: ...
    def list_by_market(self, market: str) -> List[DataSourceSpec]: ...
    def list_by_data_type(self, data_type: str) -> List[DataSourceSpec]: ...
```

#### 初始注册条目

| code | adapter_cls | supported_markets | supported_data_types |
|---|---|---|---|
| `baostock_hist` | `BaostockSource` | `("CN_A",)` | `("stock_hist_daily", "stock_hist_weekly", "stock_hist_monthly", "stock_hist_minute")` |
| `akshare_spot` | `AkshareSource` | `("CN_A",)` | `("stock_list", "stock_spot")` |
| `mairui_category` | `MairuiSource` | `("CN_A",)` | `("market_category",)` |

---

### 6.2 SchemaSpec + SchemaRegistry

#### SchemaSpec

```python
@dataclass(frozen=True)
class SchemaSpec:
    """输出格式规格，定义标准化后的字段列表和类型映射。"""
    code: str                              # 唯一标识，如 "stock_zh_a_hist"
    required_fields: tuple[str, ...]       # 必须存在的字段
    float_fields: tuple[str, ...]          # 需转为 float 的字段
    int_fields: tuple[str, ...]            # 需转为 int 的字段
    date_fields: tuple[str, ...]           # 需转为 date 的字段
    string_fields: tuple[str, ...]         # 需转为 string 的字段
    primary_keys: tuple[str, ...]          # 主键字段，用于去重校验，如 ("date", "code")
    field_order: tuple[str, ...]           # 输出字段顺序
```

#### normalize 方法

```python
class SchemaRegistry:
    # ...

    def normalize(self, code: str, df: pd.DataFrame) -> pd.DataFrame:
        """根据 schema 规格标准化 DataFrame。"""
        spec = self.require(code)
        # 1. 清理列名（strip）
        # 2. 类型转换（float_fields, int_fields, date_fields, string_fields）
        # 3. 主键空值过滤
        # 4. 按 field_order 裁剪列
        # 5. 返回标准化后的 DataFrame
```

#### 初始注册条目

| code | primary_keys | 说明 |
|---|---|---|
| `stock_zh_a_hist` | `("date", "code")` | A 股历史行情 |
| `stock_zh_a_list` | `("code",)` | A 股列表 |
| `stock_zh_a_market_category` | `("code",)` | 市场分类 |

---

### 6.3 SinkSpec + SinkRegistry

#### SinkSpec

```python
@dataclass(frozen=True)
class SinkSpec:
    """下游写入规格，定义数据写入目标和写入方式。"""
    code: str                              # 唯一标识，如 "phoenixa_stock_zh_a_hist"
    adapter_cls: Type[SinkAdapter]         # 适配器类
    target_service: str                    # 目标服务，如 "phoenixA"
    supported_data_types: tuple[str, ...]  # 支持的数据类型
```

#### SinkAdapter（抽象基类）

```python
class SinkAdapter(ABC):
    """下游写入适配器基类。"""

    @abstractmethod
    def write(self, ctx: TaskContext, df: pd.DataFrame, meta: Dict[str, Any]) -> bool:
        """将标准化后的 DataFrame 写入下游服务。"""
        ...
```

#### 初始注册条目

| code | target_service | supported_data_types |
|---|---|---|
| `phoenixa_stock_zh_a_hist` | `phoenixA` | `("stock_hist_daily", "stock_hist_weekly", ...)` |
| `phoenixa_stock_zh_a_list` | `phoenixA` | `("stock_list",)` |
| `phoenixa_market_category` | `phoenixA` | `("market_category",)` |

---

### 6.4 三层注册表之间的关系

一次下载任务的注册表条目组合：

```text
source_code = "baostock_hist"        ← 从 baostock 获取数据
schema_code = "stock_zh_a_hist"      ← 按 A 股历史行情格式标准化
sink_code   = "phoenixa_stock_zh_a_hist"  ← 写入 PhoenixA

→ DownloadPipeline(source_code, schema_code, sink_code)
```

新增"港股 ETF 历史数据下载"：

```text
source_code = "baostock_hist"              # 复用已有数据源
schema_code = "etf_hk_hist"                # 注册新 schema
sink_code   = "phoenixa_etf_hk_hist"       # 注册新 sink
```

---

## 7. 数据源适配器设计

### 7.1 BaostockSource

对应现有 `stock_zh_a_hist_child.py` 中的 `execute()` 逻辑。

```python
class BaostockSource(DataSourceAdapter):
    """Baostock 数据源适配器，封装 baostock SDK 的查询调用。"""

    def validate(self, params: Dict[str, Any]) -> List[str]:
        # 校验 code, start_date, end_date, bs_period, bs_adjust, fields 等
        ...

    def before_fetch(self, ctx, params):
        # baostock login
        lg = bs.login()
        if lg.error_code != '0':
            raise RuntimeError(f"baostock login failed: {lg.error_msg}")

    def fetch(self, ctx, params) -> pd.DataFrame:
        # bs.query_history_k_data_plus(...)
        # 返回原始 DataFrame
        ...

    def after_fetch(self, ctx, params):
        # baostock logout
        bs.logout()
```

**迁移说明**：将 `stock_zh_a_hist_child.py` 中 `execute()` 的核心逻辑抽入此适配器，`utils.py` 中的 `convert_to_baostock_params` 也移入此类。

### 7.2 AkshareSource

对应现有 `stock_zh_a_list.py` 中的 `execute()` 逻辑（通过 AmazingData SDK 间接使用 akshare）。

```python
class AkshareSource(DataSourceAdapter):
    """Akshare 数据源适配器，封装 AmazingData SDK 的调用。"""

    def validate(self, params: Dict[str, Any]) -> List[str]:
        # 校验 exchange 等参数
        ...

    def fetch(self, ctx, params) -> pd.DataFrame:
        # am_object.get_code_info(security_type=...)
        # 返回 DataFrame
        ...
```

### 7.3 MairuiSource

对应现有 `stock_zh_a_market_category.py` 中的 `execute()` 逻辑。

```python
class MairuiSource(DataSourceAdapter):
    """Mairui API 数据源适配器。"""

    def validate(self, params: Dict[str, Any]) -> List[str]:
        ...

    def fetch(self, ctx, params) -> pd.DataFrame:
        # requests.get(mairui_url)
        # 返回 DataFrame
        ...
```

---

## 8. 统一管线（DownloadPipeline）

### 8.1 设计

```python
class DownloadPipeline:
    """下载管线：组装 source + schema + sink，执行完整的 fetch → normalize → sink 流程。"""

    def __init__(self, source_code: str, schema_code: str, sink_code: str):
        self.source_spec = source_registry.require(source_code)
        self.schema_spec = schema_registry.require(schema_code)
        self.sink_spec = sink_registry.require(sink_code)

        self.source_adapter = self.source_spec.adapter_cls()
        self.sink_adapter = self.sink_spec.adapter_cls()

    def execute(self, ctx: TaskContext, params: Dict[str, Any]) -> bool:
        """
        执行完整的下载管线。
        返回 True 表示成功，False 表示失败。
        """
        # 1. 校验
        errors = self.source_adapter.validate(params)
        if errors:
            ctx.fail("; ".join(errors), phase="download_validate")
            return False

        # 2. 前置准备（如 SDK 登录）
        self.source_adapter.before_fetch(ctx, params)

        try:
            # 3. 获取数据
            raw_df = self.source_adapter.fetch(ctx, params)
            if raw_df.empty:
                ctx.logger.info({"event": "download_empty", "source": self.source_spec.code})
                return True

            # 4. 标准化
            normalized_df = schema_registry.normalize(self.schema_spec.code, raw_df)

            # 5. 写入下游
            meta = self._extract_meta(params)
            success = self.sink_adapter.write(ctx, normalized_df, meta)
            if not success:
                ctx.fail("sink failed", phase="download_sink")
                return False

            return True

        finally:
            # 6. 清理（如 SDK 登出）
            self.source_adapter.after_fetch(ctx, params)

    @staticmethod
    def _extract_meta(params: Dict[str, Any]) -> Dict[str, Any]:
        """从参数中提取写入所需的元信息。"""
        ...
```

### 8.2 管线在 TaskUnit 中的使用

WorkerUnit 的 `execute()` + `post_process()` + `sink()` 可以被管线替代：

```python
# 之前：每个 WorkerUnit 各自实现 execute + post_process + sink
class StockZhAHistChild(WorkerUnit):
    def execute(self, ctx):
        # 30+ 行：baostock 查询
        ...
    def post_process(self, ctx, df):
        # 60+ 行：schema 标准化
        ...
    def sink(self, ctx, df):
        # 30+ 行：PhoenixA 写入
        ...

# 之后：WorkerUnit 只需组装管线
class GenericDownloadWorker(WorkerUnit):
    def execute(self, ctx):
        params = ctx.params
        pipeline = DownloadPipeline(
            source_code=params["source_code"],
            schema_code=params["schema_code"],
            sink_code=params["sink_code"],
        )
        return pipeline.execute(ctx, params)
```

---

## 9. 与 task_engine/download/ 的关系

### 9.1 渐进迁移策略

```text
阶段 1（本次）：搭建 download_engine 框架
  ├── engines/download_engine/ 下创建注册表、适配器接口、管线
  ├── 不修改 engines/task_engine/download/zh/ 下的任何代码
  └── 现有 cronjob 任务继续正常运行

阶段 2：新下载任务走引擎
  ├── 新增市场（如 HK）的下载任务直接使用 download_engine
  ├── engines/task_engine/download/hk/ 下的 WorkerUnit 调用 DownloadPipeline
  └── 老任务（zh/）保持不动

阶段 3：迁移现有任务（可选）
  ├── 将 zh/ 下的任务逐步迁移到使用 download_engine
  ├── 迁移后删除各任务中的硬编码逻辑
  └── 每次迁移一个任务，确保 cronjob 不受影响
```

### 9.2 download 任务如何调用 download_engine

以新增"HK stock list 下载"为例：

```python
# engines/task_engine/download/hk/stock_hk_list.py

class StockHKListWorker(WorkerUnit):
    def execute(self, ctx):
        pipeline = DownloadPipeline(
            source_code="akshare_spot",
            schema_code="stock_hk_list",
            sink_code="phoenixa_stock_hk_list",
        )
        return pipeline.execute(ctx, ctx.params)
```

需要做的准备工作：

1. 在 `schema_registry` 注册 `stock_hk_list` schema；
2. 在 `sink_registry` 注册 `phoenixa_stock_hk_list` sink；
3. `akshare_spot` source 可能需要扩展以支持 HK 市场。

### 9.3 OrchestratorUnit（Parent）的变化

OrchestratorUnit（Parent 任务）负责编排，本身逻辑变化不大：

- 仍然负责 `parameter_check` → `load_dynamic_parameters` → `plan` → `finalize`；
- 但 `plan()` 生成的 child params 中增加了 `source_code` / `schema_code` / `sink_code`；
- Child Worker 变得更薄，只负责调用 pipeline。

---

## 10. 目录重组的完整影响评估

### 10.1 三项重组变更

| 变更 | 原路径 | 新路径 | 性质 |
|---|---|---|---|
| task_units 重命名 | `artemis/task_units/` | `artemis/engines/task_engine/` | 重命名 + 迁移 |
| bt_engine 重命名 | `task_units/bt_engine/` | `engines/task_engine/backtest/` | 重命名 |
| strategy_engine 迁移 | `artemis/strategy_engine/` | `artemis/engines/strategy_engine/` | 迁移 |

### 10.2 import 变更范围

#### task_units → engines/task_engine

| 文件 | import 变更 |
|---|---|
| `core/context.py` | `from artemis.task_units.base import ...` → `from artemis.engines.task_engine.base import ...` |
| `core/task_registry.py` | 同上 |
| `engines/task_engine/__init__.py` | 内部 import 路径更新 |
| `engines/task_engine/backtest/campaign.py` | `from artemis.task_units.orchestrator_unit import ...` → `from artemis.engines.task_engine.orchestrator_unit import ...` |
| `engines/task_engine/download/zh/*.py` | 同上 |
| `consts/task_code.py` | 无变化（TaskCode 是字符串枚举） |

#### bt_engine → backtest

| 文件 | import 变更 |
|---|---|
| `engines/task_engine/__init__.py` | `from artemis.task_units.bt_engine import ...` → `from artemis.engines.task_engine.backtest import ...` |
| `config/registrations.yaml` | module 路径更新 |

#### strategy_engine 迁移

| 文件 | import 变更 |
|---|---|
| `engines/task_engine/backtest/campaign.py` | `from artemis.strategy_engine import ...` → `from artemis.engines.strategy_engine import ...` |
| `engines/task_engine/backtest/run.py` | 同上 |

#### core/sdk 和 core/clients

无需变更。SDK 和 clients 保留在 `core/`，所有引擎通过 `core/sdk/manager.py` 和 `core/clients/` 引用。

### 10.3 不变的文件

- `core/clients/` — 全部不变；
- `core/sdk/base.py` — BaseSDK 框架不变；
- `core/config_manager.py` — 不变；
- `core/task_engine.py` — 不变（TaskEngine 本身不改，只是 task_units 重命名）；
- `core/task_registry.py` — 不变（TaskRegistry 不感知目录结构）；
- `consts/` — TaskCode、DeptServices、SDK_NAME 枚举不变；
- `api/` — 不变（API 层通过 TaskEngine 调用，不直接 import task_units）。

### 10.4 迁移时机建议

**建议在搭建 `engines/` 文件夹时一次性完成全部目录重组**：

1. 创建 `artemis/engines/` 目录；
2. 将 `task_units/` 移入并重命名为 `engines/task_engine/`；
3. 将 `bt_engine/` 重命名为 `backtest/`；
4. 将 `strategy_engine/` 移入 `engines/`；
5. 批量更新 import 路径；
6. 在旧路径保留 re-export 兼容层（可选，用于渐进迁移）。
7. `core/sdk/` 和 `core/clients/` 不变。

一次性完成可以避免后续二次迁移，变更集中在 import 路径，无逻辑变更。

---

## 11. 实施顺序建议

### Phase 1：目录重组（建议首先执行）

1. 创建 `artemis/engines/` 目录；
2. 将 `task_units/` 移入并重命名为 `engines/task_engine/`；
3. 将 `bt_engine/` 重命名为 `backtest/`；
4. 将 `strategy_engine/` 移入 `engines/`；
5. 批量更新所有 import 路径；
6. 验证现有任务（backtest、download）仍可正常运行；
7. 可选：在旧路径保留 re-export 兼容层。

### Phase 2：download_engine 框架

1. 创建 `engines/download_engine/` 目录；
2. 实现 `source_registry.py`（DataSourceSpec + DataSourceRegistry + DataSourceAdapter）；
3. 实现 `schema_registry.py`（SchemaSpec + SchemaRegistry + normalize）；
4. 实现 `sink_registry.py`（SinkSpec + SinkRegistry + SinkAdapter）；
5. 实现 `pipeline.py`（DownloadPipeline）。

### Phase 3：数据源适配器实现

1. 实现 `sources/baostock_source.py`（迁移自 `stock_zh_a_hist_child.py` 的 execute 逻辑，通过 `core/sdk/baostock_sdk.py` 调用 SDK）；
2. 实现 `sources/akshare_source.py`（迁移自 `stock_zh_a_list.py` 的 execute 逻辑，通过 `core/sdk/amazing_data_sdk.py` 调用 SDK）；
3. 实现 `sources/mairui_source.py`（迁移自 `stock_zh_a_market_category.py` 的 execute 逻辑）；
4. 注册初始条目到各注册表。

### Phase 4：新任务验证

1. 用一个新下载任务（如新市场或新品种）验证引擎可用；
2. 确认 pipeline 的 fetch → normalize → sink 流程完整跑通；
3. 确认与现有 cronjob 任务互不影响。

### Phase 5：现有任务迁移（可选）

1. 逐个将 `engines/task_engine/download/zh/` 下的任务迁移到使用 download_engine；
2. 每次迁移一个，回归测试通过后再迁移下一个；
3. 迁移完成后删除任务中的冗余代码。

---

## 12. 不做的事情（避免过度设计）

以下不在本次范围内：

- 通用下载调度框架（分布式、断点续传、流式下载）；
- 任意数据源动态加载（类似插件系统）；
- 跨服务数据流编排；
- 下载任务的可视化监控面板；
- 大规模并行下载优化；
- 自动 schema 推断（schema 仍需手动注册）。

---

## 13. 总结

| 维度 | 方案 |
|---|---|
| 目录结构 | 新增 `engines/` 层，收纳 `task_engine`、`strategy_engine`、`download_engine` |
| 重命名 | `task_units` → `engines/task_engine`，`bt_engine` → `backtest` |
| 公共设施 | `core/sdk/` 和 `core/clients/` 保持不变，所有引擎共用 |
| 扩展方式 | 三层注册表（source / schema / sink），新增下载能力 = 注册条目 |
| 核心抽象 | `DataSourceAdapter`（获取）+ `SchemaSpec`（标准化）+ `SinkAdapter`（写入） |
| 管线模式 | `DownloadPipeline.execute()` → fetch → normalize → sink |
| 迁移策略 | 增量：新任务走引擎，老任务保持不动 |
| 依赖方向 | `task_engine → 其他 engines → core`（单向） |

这个方案能收敛下载共性逻辑、避免文件爆炸、统一引擎组织结构，同时保持最小变更范围。

---

## 14. 设计缺陷与 PENDING 状态说明

> **2026-04-02 追加**：经 review 发现 Phase 2/3 的实现存在两个根本性设计缺陷，已回滚，等待重新设计。

### 14.1 缺陷一：Source 不等于 FetchOp

当前设计将一个 SDK（如 baostock）映射为一个 `DataSourceAdapter`，只暴露一个 `fetch()` 方法。但现实中 baostock 有几十个 API（K线、利润表、资产负债表、现金流量表、行业分类等），一个 `fetch()` 无法覆盖。

**需要重新设计**：将"SDK 生命周期管理"与"具体数据获取操作"拆分为两层。

### 14.2 缺陷二：Pipeline 无法承载增量/去重/拆分逻辑

当前 `DownloadPipeline`（validate → fetch → normalize → sink）是固定的线性流程，无法支持：
- 从下游获取 checkpoint（如 last_update_map）避免重复下载
- 增量计算（只下载 last_update 之后的数据）
- 拆分策略（按股票/按日期拆分为子任务）

每种数据类型的增量逻辑各不相同，不能用统一 pipeline 硬编码。

### 14.3 当前执行状态

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 1 | 目录重组（task_units → engines/task_engine, bt_engine → backtest, strategy_engine → engines/strategy_engine） | **已完成** |
| Phase 2 | download_engine 框架代码 | **已回滚，PENDING** |
| Phase 3 | 数据源适配器实现 | **已回滚，PENDING** |
| Phase 4 | 新任务验证 | **已回滚，PENDING** |
| Phase 5 | 现有任务迁移 | **未开始** |

### 14.4 后续方向

download_engine 需要重新设计核心抽象，可能的改进方向：
- **Adapter 层**：只负责 SDK 生命周期（login/logout/连接管理）
- **FetchOp 层**：每个具体数据获取操作（如 `baostock_stock_hist`、`baostock_profit`）独立注册，各自携带增量策略
- **Pipeline 可选**：简单场景可用便捷管线，复杂场景由 task_engine 中的具体任务自由组合各层能力

待策略工作台（backtest workbench）功能完成后，再回来重新设计 download_engine。
