# Skill: 新增 SDK 下载任务对接流程

> 本 skill 指导如何将一个新的数据源 SDK 接入 Chaos 平台。
> 覆盖范围：Artemis（下载引擎）→ PhoenixA（数据中台落库）→ CronJob（定时调度）→ Cthulhu（前端展示）。
> 当用户说"接入 XXX SDK 的 YYY 数据"或"新增下载任务"时，按本流程执行。

---

## 阶段 0：需求确认

在开始实现前，与用户确认以下信息：

| 确认项 | 说明 |
|--------|------|
| SDK 名称和版本 | 如 AmazingData V1.0.24 |
| 数据类型 | 行情 / 财务 / 公司行为 / 行业 / 因子 / 其他 |
| API 函数签名 | 输入参数、返回字段、是否支持 code_list |
| 数据量级 | 预估行数、单行大小，决定 tablespace 选择 |
| 增量策略 | 全量 or 增量？增量依据什么字段（日期/版本）？ |
| 是否需要 plan/child | SDK 是否只支持单股票查询（需要拆子任务）？ |

### 是否需要 OrchestratorUnit（plan/child 模式）的判断标准

- **需要 plan/child**：SDK 只支持单 symbol 查询（如 baostock 的 `query_history_k_data_plus`）
  - Parent 继承 `OrchestratorUnit`，从 PhoenixA 获取 symbol 列表，`plan()` 生成 N 个 child spec
  - Child 继承 `WorkerUnit`，下载单 symbol 数据
  - 示例：`STOCK_ZH_A_HIST_PARENT` / `STOCK_ZH_A_HIST_CHILD`

- **不需要 plan/child**：SDK 支持 `code_list` 批量查询（如 AmazingData 的 `get_balance_sheet`）
  - 直接继承 `WorkerUnit`（或 `BaseFinancialStatementTask` / `BaseCorporateActionTask`）
  - 示例：`STOCK_ZH_A_BALANCE_SHEET`, `STOCK_ZH_A_DIVIDEND`

---

## 阶段 1：阅读 SDK 文档并提取关键信息

### 必须提取的信息

1. **API 函数签名**
   ```python
   # 示例：AmazingData get_dividend
   info_data.get_dividend(
       code_list=["000001.SZ", "600519.SH"],  # 必选：代码列表
       local_path="...",                        # 必选：缓存路径
       is_local=False,                          # 可选：是否用本地缓存
       begin_date=20240101,                     # 可选：起始日期 (int)
       end_date=20240501                        # 可选：截止日期 (int)
   )
   ```

2. **返回字段列表** — 区分哪些是结构化列、哪些进 JSONB
   - 结构化列：symbol, market, date, type 等需要索引/过滤的字段
   - JSONB 字段：业务数据（如 TOTAL_ASSETS, EARNINGS_PER_SHARE 等）

3. **日期格式** — SDK 返回的是 `YYYYMMDD`（int）还是 `YYYY-MM-DD`（str）？
   - **重要**：PhoenixA 统一使用 `VARCHAR(10)` 存日期，需要在 Artemis 层标准化为 `YYYY-MM-DD`

4. **Symbol 格式** — SDK 返回的是 `000001.SZ` 还是纯代码 `000001`？
   - **重要**：PhoenixA 所有表的 symbol 字段统一存**纯代码**（如 `000001`），交易所信息用 `market` 字段
   - 在 Artemis 的 `post_process()` 中做拆分：`"000001.SZ" → symbol="000001", market="zh_a"`

5. **字段稳定性判断** — 是否应该建显式列，还是部分/全部放进 `JSONB`
   - **字段少、结构稳定、查询会直接使用** → 优先建显式列（例如：龙虎榜的 `buy_amount` / `sell_amount` / `total_volume`）
   - **字段很多、变化快、不同 type 结构差异大** → 再考虑 `data_json`
   - **不要**因为模板里有 `data_json` 就默认新增 `data_json`

---

## 阶段 2：PhoenixA 数据库设计

### 2.1 选择 Schema

| Schema | 用途 | 环境       |
|--------|------|----------|
| `security_dev` | 安全/金融相关表 | 开发环境     |
| `security` | 安全/金融相关表 | 生产环境     |
| `kg` | 知识图谱表 | 通用       |
| `public` | 系统级/元数据表 | 通用但是一般不用 |

### 2.2 选择 Tablespace（存储层级）

| 数据量级 | Tablespace | 硬件 | 场景 |
|----------|-----------|------|------|
| < 100 GB | `pg_default` (Hot) | 2TB NVMe | PGVector KNN、元数据、索引密集型查询 |
| 100 GB ~ 8 TB | `warm_storage` (Warm) | 8TB SATA SSD | 业务数据（bars、financial、strategy） |

**判断依据**：
- 时序数据（bars、因子、行业日度）→ `warm_storage` + TimescaleDB hypertable
- 查询频繁但数据量小的元数据 → `pg_default`
- JSONB 大对象 → `warm_storage`

### 2.3 创建 Migration SQL

文件位置：`/app/projects/phoenixA/migrations/postgresql/security/`

命名规范：`{NNNN}_{description}.sql`（N 为序号，如 `0009_your_new_table.sql`）

Migration 模板（通用模板，不是强制字段清单）：

```sql
-- PhoenixA PostgreSQL Migration {NNNN}: {Description}
-- Target: chaos_db, schema: security_dev / security
-- Scope: {table_name}
-- Storage tier: {warm_storage / pg_default}（依据：预估数据量 {XX} GB）
-- ============================================================

-- 1. {table_name}
CREATE TABLE IF NOT EXISTS {table_name} (
    id               BIGSERIAL      PRIMARY KEY,
    source           VARCHAR(32)    NOT NULL,
    symbol           VARCHAR(32)    NOT NULL,         -- 纯代码，如 "000001"
    market           VARCHAR(16)    NOT NULL DEFAULT 'zh_a',
    -- ... 业务特定字段 ...
    data_json        JSONB          NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_{table_name} UNIQUE (source, symbol, market, {unique_fields})
) TABLESPACE {warm_storage / pg_default};

-- B-tree indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_{abbr}_{field}
    ON {table_name} ({columns}) TABLESPACE {warm_storage / pg_default};

-- GIN index on JSONB (如果需要 JSONB 字段查询)
CREATE INDEX IF NOT EXISTS idx_{abbr}_data_gin
    ON {table_name} USING GIN (data_json) TABLESPACE {warm_storage / pg_default};
```

> **重要纠偏**：上面的 SQL 只是**通用模板**，不是要求每张新表都必须有 `id` / `data_json` / `created_at` / `updated_at`。
>
> 在设计新表时，必须先根据 SDK 返回字段做判断：
>
> - **`data_json` 仅在字段很多、结构不稳定、或需要保留大量原始扩展字段时使用**
> - **`id` 仅在确实需要单列主键时使用**（如内部引用、ORM 约束、独立对象生命周期）
> - **`created_at` / `updated_at` 仅在明确需要审计字段时使用**；不是所有明细表都必须带
> - 如果 SDK 输出字段**少而稳定**，应直接建**显式业务列**，不要机械套模板

### 2.4 字段设计规范

| 规范 | 说明 |
|------|------|
| `symbol` VARCHAR(32) | 统一存纯代码，不含交易所后缀 |
| `market` VARCHAR(16) | 交易所/市场标识：`zh_a`, `hk`, `us` 等 |
| `source` VARCHAR(32) | 数据来源：`amazing_data`, `baostock` 等 |
| 日期字段 VARCHAR(10) | 统一 `YYYY-MM-DD` 格式（如 `trade_date`, `ann_date`） |
| 业务数据 JSONB | **可选**。仅当字段很多/变化快/不适合全部建列时，才使用 `data_json` |
| `id` 主键 | **可选**。仅当需要单列主键时添加；否则可直接使用业务唯一键 |
| `created_at` / `updated_at` | **可选**。仅当需要审计/追踪更新时间时添加 |

### 2.4.1 结构化列 vs JSONB 的决策规则（强制）

在建表前，必须先做一次判断：

| 场景 | 推荐设计 |
|------|----------|
| SDK 返回字段 ≤ 20 且字段名/含义稳定 | **全部建显式列** |
| 主要查询会直接按这些字段过滤/排序/聚合 | **全部建显式列** |
| 不同子类型字段差异很大，列会非常稀疏 | 公共字段建列，其余放 `data_json` |
| 字段很多，且短期内可能频繁变更 | 可考虑 `data_json` |

**反例（不要这样做）**：
- SDK 明明只返回 8~15 个稳定字段，却仍然把金额/数量字段塞进 `data_json`
- 仅因为模板里有 `id` / `created_at` / `updated_at`，就为每张表都机械加上

### 2.5 PhoenixA Service 层（如需新表）

如果新表需要独立的 upsert API（不是复用 financial_statement / corporate_action）：

1. **Model**: `/app/projects/phoenixA/internal/model/` — 定义 Go struct
2. **DAO**: `/app/projects/phoenixA/internal/dao/` — 数据库操作
3. **Service**: `/app/projects/phoenixA/internal/service/` — 业务逻辑
4. **Controller**: `/app/projects/phoenixA/internal/controller/` — HTTP handler
5. **Router**: `/app/projects/phoenixA/internal/router/router_v2.go` — 注册路由

如果复用现有表（如 financial_statement / corporate_action），只需在 `consts/financial.go` 添加新的类型常量。

---

## 阶段 2.5：数据依赖原则 — SDK 只用于下载，依赖从 PhoenixA 获取

### 核心原则

**SDK（如 AmazingData）只用于实际数据下载。所有数据依赖必须从 PhoenixA 自有数据源获取。**

这意味着：
- 需要获取 symbol 列表？→ 调用 `PhoenixA GET /api/v2/securities`
- 需要判断某个 symbol 是否有历史数据？→ 查询 PhoenixA bars API
- 需要获取最新日期作为增量起点？→ 调用 `PhoenixA GET /api/v2/bars/{asset_type}/{market}/last_update`

**绝不要**为了获取前置数据而调用 SDK（如 `ad.BaseData().get_hist_code_list()`），这会：
1. 增加 SDK 调用次数和连接开销
2. 绕过我们自己的数据治理（PhoenixA 中的数据是经过清洗和注册的）
3. 造成数据源不一致（SDK 的列表可能和 PhoenixA 注册表不同步）

### 依赖缺失处理

如果从 PhoenixA 获取依赖时发现数据为空（如 securities 列表为空），说明**前置任务尚未执行**：
- `security_registry` 为空 → 需要先运行 `STOCK_ZH_A_LIST` 任务
- `bars_*` 表无数据 → 需要先运行 `STOCK_ZH_A_HIST_*` 任务
- 此时应记录明确的日志提示缺失的前置任务，而不是静默失败或回退到 SDK

### 代码实现方式

```python
from artemis.engines.task_engine.download.zh.utils import get_code_list_from_phoenixa

# 在 execute() 中获取 symbol 列表：
explicit_symbols = get_symbols_from_params(ctx)
if explicit_symbols is not None:
    code_list = explicit_symbols   # task.yaml 中配置了具体 symbols
    mode = 'incremental'
else:
    code_list = get_code_list_from_phoenixa(ctx)  # 从 PhoenixA 获取全部注册证券
    mode = 'full'
```

`get_code_list_from_phoenixa` 内部调用 `PhoenixAClient.get_securities()` 并转换为 SDK 格式。

---

## 阶段 3：Artemis 下载引擎实现

### 3.1 添加 TaskCode 常量

文件：`/app/projects/artemis/artemis/consts/task_code.py`

```python
class TaskCode(str, Enum):
    # ... 现有条目 ...
    YOUR_NEW_TASK = 'YOUR_NEW_TASK'
    YOUR_NEW_TASK_CHILD = 'YOUR_NEW_TASK_CHILD'  # 如果需要 plan/child
```

### 3.2 实现下载任务类

文件位置：`/app/projects/artemis/artemis/engines/task_engine/download/zh/`

#### 模式 A：财务报表类（复用 BaseFinancialStatementTask）

```python
"""下载 XXX 数据（来源：AmazingData InfoData get_xxx）。

支持增量下载参数（ctx.params）：
  - symbols: list[str]  — 指定证券代码
  - start_date / end_date: YYYY-MM-DD — 报告期范围
"""
from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHAYourNewTask(BaseFinancialStatementTask):
    STATEMENT_TYPE = "your_statement_type"   # 对应 financial_statement.statement_type
    SDK_METHOD_NAME = "get_your_data"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_your_data(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)
```

#### 模式 B：公司行为类（复用 BaseCorporateActionTask）

```python
"""下载 XXX 数据（来源：AmazingData InfoData get_xxx）。

支持增量下载参数（ctx.params）：
  - symbols: list[str]  — 指定证券代码
  - begin_date / end_date: int YYYYMMDD — 公告日期范围
"""
from artemis.engines.task_engine.download.zh.base_corporate_action import BaseCorporateActionTask


class StockZHAYourNewAction(BaseCorporateActionTask):
    ACTION_TYPE = "your_action_type"          # 对应 corporate_action.action_type
    REPORT_PERIOD_FIELD = "YOUR_PERIOD_COL"   # SDK 返回的年度/期间字段名
    PROGRESS_FIELD = "YOUR_PROGRESS_COL"      # SDK 返回的进度字段名

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_your_action(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)
```

#### 模式 C：全新数据类型（继承 WorkerUnit，自写全流程）

```python
"""下载 XXX 数据（来源：{SDK_NAME}）。

支持参数：
  - symbols: list[str] + exchange: str — 股票代码
  - start_date / end_date: YYYY-MM-DD — 日期范围
"""
import json
from typing import Any, Dict, List
from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_symbols_from_params, get_sdk_date_kwargs


class StockZHAYourNewTask(WorkerUnit):
    """完整的 WorkerUnit 实现，适用于全新数据类型。"""

    def before_execute(self, ctx: TaskContext) -> None:
        # 初始化 SDK 连接等
        pass

    def execute(self, ctx):
        # 1. 解析参数 (get_symbols_from_params, get_sdk_date_kwargs)
        # 2. 调用 SDK
        # 3. 返回原始结果
        pass

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        # 1. 从 SDK 结果中提取结构化字段
        # 2. 规范化：
        #    - symbol: "000001.SZ" → "000001"
        #    - dates: "20260425" → "2026-04-25"
        # 3. 剩余字段打包进 data_json
        pass

    def sink(self, ctx, processed):
        # 调用 PhoenixA HTTP API 批量写入
        pass

    def finalize(self, ctx: TaskContext):
        # 清理资源
        pass
```

#### 模式 D：Plan/Child（OrchestratorUnit）

适用于 SDK 只支持单 symbol 查询的场景。

**Parent（OrchestratorUnit）**：
```python
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


class StockZHAYourNewParent(OrchestratorUnit):
    def parameter_check(self, ctx):
        # 验证必要参数
        pass

    def load_dynamic_parameters(self, ctx):
        # 从 PhoenixA 获取 symbol 列表
        pass

    def before_execute(self, ctx):
        # SDK 初始化
        pass

    def plan(self, ctx) -> list:
        # 为每个 symbol 生成 child spec
        return [
            {"key": TaskCode.YOUR_TASK_CHILD, "params": child_params}
            for symbol in symbols
        ]

    def finalize(self, ctx):
        # 清理
        pass
```

**Child（WorkerUnit）**：参照模式 C 实现。

### 3.3 关键数据处理规范

| 数据标准化 | 转换规则 | 代码位置 |
|-----------|----------|---------|
| symbol 拆分 | `"000001.SZ"` → `symbol="000001"`, `market="zh_a"` | `post_process()` |
| 日期标准化 | `"20260425"` → `"2026-04-25"` | `post_process()` |
| NaN 处理 | `pd.isna(val)` → 跳过或设为空字符串 | `post_process()` |
| 数值类型 | `numpy.int64` → Python `int`（`val.item()`） | `post_process()` |

### 3.4 注册任务

**文件 1**：`/app/projects/artemis/artemis/engines/task_engine/download/zh/__init__.py`
```python
from artemis.engines.task_engine.download.zh.stock_zh_a_your_task import StockZHAYourNewTask
# 添加到 __all__
```

**文件 2**：`/app/projects/artemis/artemis/engines/task_engine/__init__.py`
```python
from artemis.engines.task_engine.download.zh import StockZHAYourNewTask

registry.register(
    TaskCode.YOUR_NEW_TASK,
    module=StockZHAYourNewTask.__module__,
    class_name=StockZHAYourNewTask.__name__,
)
```

---

## 阶段 4：更新 task.yaml 配置

文件：`/app/projects/artemis/config/task.yaml`

```yaml
  # Your New Task
  # SDK: {SDK_NAME} {SDK_METHOD}
  # 支持 code_list 批量下载
  # symbols: AmazingData 格式代码列表（如 "000001.SZ"），缺省则全量
  # start_date/end_date: 对应 SDK 的日期范围
  YOUR_NEW_TASK:
    variants:
      - match: {}
        config:
          start_date: null                     # "YYYY-MM-DD" 或 null（不限）
          end_date: null                       # "YYYY-MM-DD" 或 null（不限）
          # symbols: ["000001.SZ", "600519.SH"]  # 指定代码列表，缺省则全量
          # exchange: "SZ"                        # 与 symbols 配合使用
```

### 配置字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbols` | `list[str]` | SDK 格式代码列表。有值时增量模式，缺省时全量模式 |
| `exchange` | `str` | 交易所过滤。与 symbols 配合使用（如 `SH`, `SZ`, `BJ`） |
| `start_date` | `str or null` | 起始日期，YYYY-MM-DD 格式 |
| `end_date` | `str or null` | 截止日期，YYYY-MM-DD 格式 |
| `period` | `str` | 周期（仅行情任务） |
| `adjust` | `str` | 复权类型（仅行情任务） |

---

## 阶段 5：CronJob 任务配置

CronJob 通过 HTTP API 创建定时任务。每个下载任务需要配置调度规则。

### 5.1 任务模板

通过 CronJob 的 `POST /api/v1/tasks` API 创建任务：

```json
{
  "name": "daily_{task_name}",
  "description": "每日下载 {description}",
  "cron_expr": "0 0 18 * * 1-5",
  "exec_type": "SYNC",
  "method": "POST",
  "target_service": "artemis",
  "target_path": "/api/v1/tasks/run/{TASK_CODE}",
  "body_template": "{}",
  "concurrency_policy": "SKIP",
  "status": "ENABLED"
}
```

### 5.2 常用调度规则

| 调度需求 | cron_expr | 说明 |
|----------|-----------|------|
| 每交易日 18:00 | `0 0 18 * * 1-5` | 周一到周五 |
| 每交易日 20:00 | `0 0 20 * * 1-5` | A股收盘后 |
| 每周六 02:00 | `0 0 2 * * 6` | 周末批量 |
| 每月1号 03:00 | `0 0 3 1 * *` | 月度任务 |
| 仅一次 | 通过 API 手动触发 | 不设 cron |

### 5.3 exec_type 选择

| 类型 | 场景 |
|------|------|
| `SYNC` | 简单下载任务，执行时间 < 5 分钟 |
| `ASYNC` | plan/child 模式，需要异步执行和回调 |

> **注意**：plan/child 模式的 Parent 任务应设为 `ASYNC`，因为子任务可能很多。

### 5.4 并发策略

| 策略 | 场景 |
|------|------|
| `SKIP` | 默认，上一轮未完成时跳过本轮 |
| `QUEUE` | 必须顺序执行的任务 |
| `PARALLEL` | 允许并行（通常不用） |

### 5.5 创建 CronJob 任务导入文件

文件位置：`/app/projects/artemis/artemis/engines/task_engine/download/tasks_export_{date}.json`

每次新增下载任务时，需要创建一个新的 tasks export JSON 文件，供 CronJob 导入。

命名规范：`tasks_export_YYYY-MM-DD.json`（日期为创建日）

文件格式：
```json
{
  "exported_at": "2026-05-11T16:00:00Z",
  "version": "1.0",
  "description": "Brief description of new tasks",
  "tasks": [
    {
      "name": "task_name_snake_case",
      "description": "Task description",
      "cron_expr": "0 0 18 ? * SAT",
      "timezone": "Asia/Shanghai",
      "target_service": "artemis",
      "target_path": "/tasks/run/TASK_CODE",
      "method": "POST",
      "body_template": "{}",
      "headers_json": "{}",
      "exec_type": "ASYNC",
      "callback_method": "POST",
      "callback_timeout_sec": 3600,
      "concurrency_policy": "SKIP",
      "max_concurrency": 1,
      "overlap_action": "SKIP",
      "failure_action": "RUN_NEW",
      "retry_policy_json": "{\"max_attempts\": 2, \"initial_backoff\": \"120s\"}",
      "status": "ENABLED"
    }
  ]
}
```

**注意**：
- plan/child 模式只需要 Parent 任务的 cron entry（Child 由 Parent 自动调度）
- `callback_timeout_sec` 根据数据量设定：简单任务 1800s, plan/child 3600s+
- `target_path` 使用 Parent 的 TaskCode（如 `/tasks/run/STOCK_ZH_A_BS_BALANCE_PARENT`）

---

## 阶段 6：PhoenixA Catalog 注册与领域分类

新表需要在 Data Catalog 中展示时，更新静态元数据注册表。

### 6.1 领域分类决策树

```
新数据属于哪个领域？
│
├── 行情数据（K线/OHLCV/技术指标）→ domain = "bars"
│   └── 表名以 bars_ 或 bars_ext_ 开头
│
├── 证券基础信息（股票列表/注册信息）→ domain = "security"
│   └── 如 security_registry
│
├── 分类/行业数据（行业成分/权重/分类映射）→ domain = "taxonomy"
│   └── 如 taxonomy_*, industry_*
│
├── 财务/公司行为（财报/分红/配股/业绩预告）→ domain = "financial"
│   ├── financial_statement（三表+快报+预告）
│   └── corporate_action（分红/配股）
│
├── 策略回测数据 → domain = "strategy"
│   └── strategy_run_*
│
├── 知识图谱数据（文档/抽取/事件/影响）→ domain = "kg"
│   └── schema = kg
│
├── 因子数据 → domain = "factor"
│   └── 表名以 factor_ 开头
│
├── 市场状态/情绪数据 → domain = "regime"
│   └── 表名以 regime_ 开头
│
└── 以上都不匹配？
    ├── 检查是否是现有领域的子集 → 复用已有 domain
    └── 确实是全新数据类型 → 新建 domain（需同步更新 domainDescriptions）
```

**何时新建 domain？**
- 数据的来源、用途、查询模式与所有现有 domain 都不同
- 例：如果将来接入"宏观经济指标"数据（GDP/CPI/PMI），应新建 domain = "macro"

**何时复用现有 domain？**
- 数据用途和查询模式与已有 domain 相似
- 例：如果要加一个新的"业绩快报"表，虽然字段不同，但属于财务报表类 → 复用 "financial"

### 6.2 更新代码

文件：`/app/projects/phoenixA/internal/service/catalog_service.go`

**1. tableMetaRegistry**（必需）

```go
// 精确匹配（表名完全一致）
"your_table_name": {
    Domain:      "your_domain",
    Description: "表描述",
    TimeColumn:  "trade_date",  // 时间列名（可选，有时序数据时必填）
    Lineage: &model.DataLineage{
        SourceSystem:    "artemis",
        IngestionMethod: "REST API batch upsert",
        RefreshSchedule: "每日增量",
        APIEndpoint:     "POST /api/v2/your-endpoint/upsert",
    },
},

// 前缀匹配（表名以某个前缀开头的都用这条规则）
"your_prefix_": {
    Domain:      "your_domain",
    Description: "前缀类表描述",
    TimeColumn:  "trade_date",
    Lineage: &model.DataLineage{...},
},
```

**2. columnDescRegistry**（建议）

```go
// 通配符描述（所有表的 symbol 字段都显示这个描述）
"*.your_column": "字段描述",
// 表级描述（特定表的字段）
"your_table.your_column": "特定表的字段描述",
```

**3. domainDescriptions**（仅新建 domain 时）

```go
var domainDescriptions = map[string]string{
    // ... 现有条目 ...
    "your_new_domain": "新领域描述",
}
```

### 6.3 注册数据能力（Capability）— 必需

文件：`/app/projects/phoenixA/internal/service/catalog_service.go` → `tableCapabilityRegistry`

当新增一个下载任务时，**必须**在 `tableCapabilityRegistry` 中注册该表的数据能力描述。
这是 `/api/v2/catalog/capabilities` 接口的数据来源，LLM 和因子引擎通过此接口
自动发现"当前系统有哪些数据可用"。

**如果是复用已有表（如 financial_statement 新增 statement_type）**：
在现有 capability 的 `DataTypes` 中追加一条：

```go
// 在 tableCapabilityRegistry["financial_statement"].DataTypes 中追加：
{TypeValue: "your_new_type", Label: "新类型名", Description: "描述", Source: "baostock"},
```

**如果是全新表**：

```go
"your_table_name": {
    Provider:            "数据名称",
    ProviderDescription: "这个表/接口能提供什么数据，LLM 和因子引擎可以据此判断数据可用性",
    DataTypes: []model.DataTypeInfo{
        {TypeValue: "type_a", Label: "类型A", Description: "...", Source: "baostock"},
    },
    OutputFields: []model.FieldDesc{
        {Name: "symbol", Type: "varchar(32)", Description: "证券代码"},
        // ... 所有输出字段
    },
    QueryParams: []model.ParamDesc{
        {Name: "symbol", Type: "string", Required: false, Description: "证券代码"},
        // ... 查询参数
    },
    RefreshSchedule:     "每日增量",
    CoverageDescription: "A股全量，XXXX至今",
},
```

**注册后效果**：
- `GET /api/v2/catalog/capabilities` 自动展示新数据能力
- `GET /api/v2/catalog/data-dictionary` 会附带 capability + per-source 统计信息
- 当数据写入后，per-source 统计（行数、代码数、日期范围）自动从 DB 查询，无需手动维护

---

## 阶段 7：测试验证

### 7.1 Artemis 层测试

```bash
# 手动触发单次下载
curl -X POST http://localhost:8084/api/v1/tasks/run/YOUR_TASK_CODE \
  -H 'Content-Type: application/json' \
  -d '{"start_date": "2026-01-01", "end_date": "2026-05-01", "symbols": ["000001"], "exchange": "SZ"}'
```

### 7.2 PhoenixA 数据验证

```sql
-- 检查数据是否正确写入
SELECT COUNT(*) FROM security_dev.your_table;
SELECT * FROM security_dev.your_table LIMIT 5;

-- 验证日期格式（应该是 YYYY-MM-DD）
SELECT DISTINCT ann_date FROM security_dev.your_table LIMIT 10;

-- 验证 symbol 格式（应该是纯代码，无后缀）
SELECT DISTINCT symbol FROM security_dev.your_table LIMIT 10;

-- 验证 JSONB 数据完整性
SELECT data_json FROM security_dev.your_table LIMIT 1;
```

### 7.3 端到端验证

```bash
# 检查 Data Catalog 是否展示新表
curl http://localhost:8085/api/v2/catalog/tables | python3 -m json.tool | grep your_table

# 检查表详情
curl http://localhost:8085/api/v2/catalog/tables/security_dev/your_table | python3 -m json.tool
```

---

## 检查清单

完成以下所有步骤才算对接完成：

- [ ] **阶段 0**：需求确认（SDK 文档、数据量、增量策略）
- [ ] **阶段 1**：SDK 文档分析（API 签名、字段列表、日期/symbol 格式）
- [ ] **阶段 2**：PhoenixA Migration SQL
  - [ ] 正确选择 schema（security_dev / security / kg ）
  - [ ] 正确选择 tablespace（pg_default / warm_storage）
  - [ ] symbol 字段存纯代码
  - [ ] 日期字段统一 YYYY-MM-DD 格式
  - [ ] JSONB + GIN 索引
  - [ ] UNIQUE 约束设计正确（保证幂等 upsert）
- [ ] **阶段 3**：Artemis 下载引擎
  - [ ] 添加 TaskCode 常量
  - [ ] 实现任务类（选择正确的基类模式 A/B/C/D）
  - [ ] symbol 拆分（"000001.SZ" → "000001"）
  - [ ] 日期标准化（"20260425" → "2026-04-25"）
  - [ ] 注册到 `__init__.py`
- [ ] **阶段 4**：task.yaml 配置
  - [ ] 所有支持的参数都有注释说明
  - [ ] symbols / exchange / start_date / end_date 配置完整
- [ ] **阶段 5**：CronJob 任务配置
  - [ ] 调度时间合理（考虑数据源更新时间）
  - [ ] exec_type 正确（SYNC / ASYNC）
  - [ ] 并发策略合理
  - [ ] **创建 `tasks_export_{date}.json` 文件**（在 `download/` 目录下）
- [ ] **阶段 6**：PhoenixA Catalog 注册
  - [ ] tableMetaRegistry 更新
  - [ ] columnDescRegistry 更新（常用列）
  - [ ] domainDescriptions 更新（新 domain）
  - [ ] **tableCapabilityRegistry 更新（数据能力描述）**— 必需！
- [ ] **阶段 7**：测试验证
  - [ ] 单次手动下载成功
  - [ ] PhoenixA 数据格式正确（symbol、日期）
  - [ ] Data Catalog 展示正常
- [ ] **文档更新**：CHANGELOG 更新（**必须用英语书写**）
  - [ ] **API 业务数据文档更新**：更新 `app/projects/phoenixA/docs/api_biz_data_description/` 目录
    - [ ] 判断新数据应放入哪个文档：
      - 公司行为数据（分红、配股等）→ 更新 `corporate_actions.md`
      - 财务报表数据（资产负债表、利润表等）→ 更新 `financial_statements.md`
      - 行业数据 → 更新 `taxonomy.md`
      - 证券基础信息 → 更新 `securities.md`
      - 行情数据 → 更新 `bars.md`
      - 全新类型 → 创建新的 `{feature_name}.md` 文件
    - [ ] 如果是新增 statement_type 或 action_type（复用现有表）：
      - [ ] 在对应文档的 type 列表中追加新类型
      - [ ] 添加 data_json 字段结构表格，**类型必须准确**：
        - 整数类型使用 `integer`（如 `IS_CHANGED`: 1/0）
        - 浮点类型使用 `number`（如 `TOTAL_ASSETS` 货币金额、百分比等）
        - 字符串类型使用 `string`
        - 布尔类型使用 `boolean`
        - 参考 `/app/projects/artemis/artemis/consts/field_catalog.py` 获取准确类型定义
      - [ ] 添加示例数据
    - [ ] 如果是全新表：
      - [ ] 创建独立的 `{feature_name}.md` 文件
      - [ ] 按照现有文档模板编写：概述、API 端点、查询参数、响应数据、响应示例
      - [ ] 确保字段类型与底层存储（PostgreSQL/Migration SQL）和 field_catalog.py 保持一致
    - [ ] 更新 `README.md` 索引文件，添加新文档的链接
    - [ ] **重要**：字段不要增加、减少、改变，确保与原有文档结构和底层数据一致
    - [ ] **类型准确性**：避免使用模糊的 `number`/`number64` 类型，明确区分 `integer` 和 `number`
  - [ ] **数据表参考文档更新**：更新 `app/projects/phoenixA/docs/tables_description/` 目录（可选，用于数据库层参考）
    - [ ] 判断新数据应放入哪个拆分文档：
      - 公司行为数据（分红、配股等）→ 更新 `corporate_action.md`
      - 财务报表数据（资产负债表、利润表等）→ 更新 `financial_statement.md`
      - 行业指数数据 → 更新 `industry_base_info.md` / `industry_constituent.md` / `industry_weight.md` / `industry_daily.md`
      - 全新类型（非上述分类）→ 创建新的 `{table_name}.md` 文件
    - [ ] 更新 `index.md` 索引文件，添加新表的链接
    - [ ] 字段不要增加、减少、改变，确保与原有文档结构一致
  - [ ] **数据表参考文档更新**：更新 `docs/2026-05-12 DATA_TABLES_REFERENCE.md`（可选，保留作为完整参考）
    - [ ] 更新"待完善内容"清单，将新表标记为已完成

---

## 文件路径快速索引

| 类别 | 文件路径 |
|------|---------|
| SDK 文档 | `/docs/AmazingData_development_guide.md` |
| 数据表参考文档（拆分后） | `app/projects/phoenixA/docs/tables_description/` |
| 平台设计 | `/docs/2026-04-29 DESIGN_OF_FINANCIAL_QUANT_PLATFORM.md` |
| 基础设施 | `/docs/2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md` |
| PostgreSQL | `/docs/2026-04-30 INSTALL_AND_CONFIG_POSTGRESQL.md` |
| Artemis TaskCode | `/app/projects/artemis/artemis/consts/task_code.py` |
| Artemis 任务注册 | `/app/projects/artemis/artemis/engines/task_engine/__init__.py` |
| Artemis download init | `/app/projects/artemis/artemis/engines/task_engine/download/zh/__init__.py` |
| Artemis 工具函数 | `/app/projects/artemis/artemis/engines/task_engine/download/zh/utils.py` |
| Artemis 财务基类 | `/app/projects/artemis/artemis/engines/task_engine/download/zh/base_financial_statement.py` |
| Artemis 公司行为基类 | `/app/projects/artemis/artemis/engines/task_engine/download/zh/base_corporate_action.py` |
| Artemis config | `/app/projects/artemis/config/task.yaml` |
| CronJob task exports | `/app/projects/artemis/artemis/engines/task_engine/download/tasks_export_*.json` |
| PhoenixA migrations | `/app/projects/phoenixA/migrations/postgresql/security/` |
| PhoenixA Catalog | `/app/projects/phoenixA/internal/service/catalog_service.go` |
| PhoenixA consts | `/app/projects/phoenixA/internal/consts/financial.go` |
| CronJob task model | `/app/projects/cronjob/internal/model/task.go` |
| 存储规划 | `/docs/2026-05-09 STORAGE_TIER_PLANNING.md`（如存在） |
