# 第一个财务因子 Hands-On 指南：资产负债率（debt_to_assets）

> 日期：2026-07-20
> 状态：Draft（待审批后开工）
> 范围：在已验收的 Feature Platform 上新增第一个真实财务因子，作为 Financial Feature Pack V1 的起点
> 上游基线：
> - [Feature Platform 架构设计与分阶段迭代方案](./2026-07-14%20FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md)
> - [Phase 1 执行报告](./2026-07-14%20FEATURE_PLATFORM_PHASE_1_EXECUTION_REPORT.md)
> - [Phase 2 执行报告](./2026-07-14%20FEATURE_PLATFORM_PHASE_2_EXECUTION_REPORT.md)
> - [Phase 5 验收报告](./2026-07-18%20FEATURE_PLATFORM_PHASE_5_ACCEPTANCE_REPORT.md)
> - [FeaturePlugin 开发者指南](./2026-07-18%20FEATURE_PLUGIN_DEVELOPER_GUIDE.md)
> 目标读者：因子研究开发者、后端开发、评审者

---

## 0. 文档目的

Feature Platform Phase 0~5 已验收完成，受信开发网络内财务因子迭代已解锁。本文是**第一个财务因子**的落地指南：选定因子、解释选择理由、给出逐步操作流程与代码骨架，并附带背景概念速查与代码阅读路径。

本文不重复架构设计与开发者指南的内容，只在二者基础上给出**具体因子、具体字段、具体文件路径和具体 PIT 口径**。读者应先读过开发者指南再按本文操作。

---

## 1. 背景概念与代码导读

> 本节给不熟悉 Feature Platform 的人：先讲清核心术语，再讲清 Catalog/Manifest/Plugin/平台代码的关系，再说明哪些操作有 UI、哪些只能 curl，最后给一条分层代码阅读路径。

### 1.1 术语速查

#### PIT（Point-in-Time，时点）

量化里特指"站在某个时间点，只能用那个时间点之前**已经公开**的信息"。它要解决的是**未来信息泄漏**（look-ahead bias）--回测时如果用了当时还不存在的信息，回测结果就是假的。

财务报表的 PIT 关键：用**公告日**判断可见性，不是**报告期**。

> 例子：某公司 2025 年报，报告期是 `2025-12-31`，但 `2026-04-15` 才公告。如果你的观察时点是 `2026-03-01`，这份年报在那时**还不存在**，不能用。**报告期 ≠ 信息可用时间**。

在平台里：provider 用 `available_at = actual_ann_date 否则 ann_date`，`available_at > data_cutoff_time` 的记录被丢弃；PhoenixA 服务层和数据库 trigger 双重拒绝越界写入。

#### as_of_time（观察时点）

"你站在什么时候看这个世界"。是研究/分析的语义时间。值的描述时间 `observed_at` 通常等于它。

> 例子：系统在 `2026-08-15` 跑一个"站在 `2026-08-01` 收盘后观察"的截面。`as_of_time = 2026-08-01`，`computed_at = 2026-08-15`。`computed_at` 只是何时执行，不改变观察视点。

#### cutoff（data_cutoff_time，数据截止时间）

允许使用的最大信息可用时间。约束：`data_cutoff_time <= as_of_time`。

通常等于 `as_of_time`，但可以更早（更保守）。比如你站在 T 日观察，但只想用 T-1 日收盘前可用的数据，这时 `cutoff < as_of_time`。任何输入数据的 `available_at` 必须 `<= data_cutoff_time`。

#### manifest.yaml（catalog 索引）

列出"要加载哪些 feature manifest 文件"的清单。Loader **只读**这个文件里列出的路径，不扫描目录--**不注册 = 不加载**。路径解析后必须仍在 catalog root 内，防 `../` 逃逸。注意它本身不是某个 feature 的 manifest，而是"manifest 的清单"，命名容易混。

#### feature-manifest.schema.json

JSON Schema（Draft 2020-12），定义"一个 feature manifest 文件"的结构契约，用于 CI/编辑器校验。和 `domain/models.py` 里的 Pydantic `FeatureManifest` 是**双重契约**：JSON Schema 声明式（CI 用），Pydantic 运行时（loader 用），两者必须一致。

### 1.2 Catalog / Manifest / Plugin / 平台代码 的关系

```text
config/feature_catalog/                    ← Catalog（目录）：所有定义的家
├── manifest.yaml                          ← 索引：列出加载哪些 manifest
├── schema/feature-manifest.schema.json    ← 契约：manifest 的结构
└── features/<domain>/<feature>.yaml       ← Manifest：每个描述一个 FeatureVersion

artemis/feature_platform/plugins/<...>.py  ← Plugin：manifest 里 entrypoint 指向的 Python 类，真正算数

artemis/feature_platform/**                ← 平台代码（runtime 引擎）
├── manifests/   loader / validator / checksum
├── planning/    DAG / 环检测 / 拓扑序
├── execution/   executor / runner / 输出校验
├── providers/   phoenixa（拉数据，PIT 权威过滤）
├── storage/     phoenixa_writer（写值）
├── registry/    client（调 PhoenixA API）
└── tasks/       feature_compute_task（七阶段）
```

一句话：**Catalog 是定义仓库（Git/YAML），Manifest 是某个版本的说明书，Plugin 是说明书指定的执行者，平台代码是"读说明书 -> 找执行者 -> 喂数据 -> 跑 -> 收结果 -> 写库"的运行时引擎，PhoenixA 是权威存储。**

跑一次 compute 的数据流：

1. 启动时 loader 读 `manifest.yaml` -> 加载所有 manifest -> schema/pydantic 校验 -> 算 checksum
2. `POST /features/registry/sync` -> manifest 投影到 PhoenixA `govern.feature_*` 表（Definition/Version/Implementation/Dependency）
3. `POST /features/compute` -> PhoenixA 建 Run -> Artemis TaskEngine 提交 ASYNC Task
4. Task 内：Planner 解析依赖图 -> Executor 加载 plugin -> provider 拉数据 -> `plugin.compute` -> 输出校验 -> writer 写 NumericValue 到 PhoenixA
5. 查询：`GET /api/v2/features/values/numeric/*` 从 PhoenixA `dwd.feature_value_numeric` 读

### 1.3 哪些操作有 UI，哪些只能 curl

Cthulhu 前端是**「只读 + 手工触发」的诊断台，不是开发台**（架构设计本轮明确"Cthulhu 不提供在线编辑或发布"）。从 `app/projects/cthulhu/src/app/features/feature-platform/services/feature-platform-api.service.ts` 代码确认：

| 操作 | UI 能做？ | 在哪 / 怎么做 |
|---|---|---|
| 浏览 Registry / Definition / Versions / Lineage / Availability | ✅ | `/workbench/features/registry`、`/definitions/:code`、`/lineage/:code` |
| 浏览 Runs / Run Detail | ✅ | `/workbench/features/runs`、`/runs/:runId` |
| 查询 Values（横截面/时序图） | ✅ | `/workbench/features/values` |
| **手工触发 Compute** | ✅ | `/workbench/features/compute`（完整表单：feature/version/source/market/as-of/cutoff/security_ids/idempotency/retry/force） |
| **校验 manifest**（validate） | ❌ 只能 curl | Step 6，开发/CI 动作 |
| **同步 Registry**（sync） | ❌ 只能 curl | Step 7，运维动作 |
| **发布/废弃版本**（publish/deprecate） | ❌ 只能 curl | Step 7，版本治理动作 |
| **创建 BackfillJob** | ❌ 只能 curl | Step 10，运维动作 |

所以本文 Step 8（compute）和 Step 9（查询值）**完全可以在 UI 做**；Step 6/7/10（validate/sync/publish/backfill）只能 curl。原因：UI 服务里唯一的 POST 方法就是 `compute()`，没有 sync/validate/publish/backfill 的方法。

### 1.4 怎么读代码（分层阅读路径）

Feature Platform 代码量大，不要一上来钻进某个 3000 行 controller。建议按下面 8 站顺序读，每站只看标注的文件和关注点，边读边用 `constant_one` 跑一次 E2E 对照日志。

#### 第 1 站：数据模型（先懂"是什么"）

- `docs/system_design/2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md` §6 领域模型--FeatureDefinition / Version / Implementation / Dependency / Run / RunItem / RunSubject / Value 的关系图。
- `app/projects/phoenixA/migrations/postgresql/security/0008_feature_platform.sql`--真实表结构、唯一约束、`dwd.feature_value_numeric` hypertable、cutoff trigger。这是 PhoenixA 控制面的"地基"。
- `app/projects/artemis/artemis/feature_platform/domain/models.py`--Artemis 侧 Pydantic 契约（`FeatureManifest`、`FeatureDependencySpec`、`NumericValue`、`FeatureNumericOutput`）。

关注：哪些字段不可变、哪些状态机、`source_max_available_at` 为什么必填。

#### 第 2 站：Manifest 与 Catalog（再懂"怎么定义"）

- `app/projects/artemis/config/feature_catalog/manifest.yaml`--索引。
- `app/projects/artemis/config/feature_catalog/features/platform/constant_one.yaml`--最简单的 manifest（无依赖）。
- `app/projects/artemis/config/feature_catalog/features/platform/datafield_pit_probe.yaml`--带 DataField 依赖的 manifest。
- `app/projects/artemis/config/feature_catalog/schema/feature-manifest.schema.json`--JSON Schema 契约。
- `app/projects/artemis/artemis/feature_platform/manifests/loader.py`--怎么加载、防路径逃逸。
- `app/projects/artemis/artemis/feature_platform/manifests/validator.py`--校验规则、entrypoint 导入。
- `app/projects/artemis/artemis/feature_platform/manifests/checksum.py`--canonical checksum（跨语言对齐 PhoenixA Go）。

关注：Manifest 字段如何映射到 PhoenixA 投影；checksum 为什么必须稳定。

#### 第 3 站：Plugin 协议（再懂"怎么算"）

- `app/projects/artemis/artemis/feature_platform/execution/protocol.py`--`FeaturePlugin` 四方法协议（validate / load_inputs / compute / validate_output）。
- `app/projects/artemis/artemis/feature_platform/execution/context.py`--`FeatureExecutionContext` 字段（`feature_version_id`、`as_of_time`、`data_cutoff_time`、`security_ids`、`implementation_config`）。
- `app/projects/artemis/artemis/feature_platform/plugins/smoke/constant_one.py`--最简插件，30 行看懂协议。
- `app/projects/artemis/artemis/feature_platform/plugins/smoke/datafield_pit_probe.py`--PIT 选样插件，是本指南 `debt_to_assets` 的直接模板。
- `app/projects/artemis/artemis/feature_platform/execution/python_executor.py`--平台怎么调插件（daemon thread + 超时 + 异常映射），看 `_invoke`。
- `app/projects/artemis/artemis/feature_platform/execution/output_validator.py`--输出校验（universe / 类型 / NaN / 覆盖率 / 重复）。

关注：plugin 拿不到数据库连接，只能通过 provider 读数据、返回 typed output；平台 writer 是唯一写入口。

#### 第 4 站：Provider（再懂"怎么喂数据"）

- `app/projects/artemis/artemis/feature_platform/providers/base.py`--`DataFieldRecord` / `DataFieldBatch` / `FeatureDataProvider` 协议。
- `app/projects/artemis/artemis/feature_platform/providers/phoenixa.py`--**PIT 权威过滤就在这里**（`_available_at`、`load_data_field`）。看它为什么不用 `ann_date_before` 当防线。

关注：每个 dependency 一次 fetch；`available_at > cutoff` 的记录被丢弃；返回记录带 `reporting_period` / `metadata`。

#### 第 5 站：Planner（再懂"怎么排依赖"）

- `app/projects/artemis/artemis/feature_platform/planning/graph.py`--依赖图构建。
- `app/projects/artemis/artemis/feature_platform/planning/cycle_detector.py`--环检测（排序遍历，稳定 cycle path）。
- `app/projects/artemis/artemis/feature_platform/planning/execution_plan.py`--拓扑序、plan checksum。

关注：精确版本解析（禁止 `latest`）、二次 cycle 检测、plan checksum 冻结进 Run。

#### 第 6 站：Task 全流程（再懂"怎么串起来跑"）

- `app/projects/artemis/artemis/feature_platform/tasks/feature_compute_task.py`--`BaseTaskUnit` 七阶段映射（parameter_check / load_dynamic_parameters / before_execute / execute / post_process / sink / finalize）。**这是理解一次 Run 生命周期的主轴**。
- `app/projects/artemis/artemis/feature_platform/registry/client.py`--调 PhoenixA API 的 HTTP client（sync / resolve / run / value / `query_financial_flat`）。
- `app/projects/artemis/artemis/feature_platform/storage/phoenixa_writer.py`--批量写 NumericValue。

关注：Run 状态机（queued -> planning -> running -> validating -> succeeded）、heartbeat、失败清理。

#### 第 7 站：HTTP 入口与 PhoenixA 控制面（再懂"服务边界"）

- `app/projects/artemis/artemis/api/http_gateway/feature_routes.py` + `app/projects/artemis/artemis/services/feature_service.py`--Artemis 侧 4 个 API（compute / executions / manifests/validate / registry/sync）。
- `app/projects/phoenixA/internal/api/router_v2.go`--PhoenixA `/api/v2/features/*` 路由注册。
- `app/projects/phoenixA/internal/controller/feature_controller.go`--HTTP 边界。
- `app/projects/phoenixA/internal/service/feature_registry_service.go`--Registry sync / publish / 依赖解析 / 环检测。
- `app/projects/phoenixA/internal/service/feature_run_service.go`--Run 状态机、PIT/cutoff、批量幂等写。
- `app/projects/phoenixA/internal/dao/feature_registry_dao.go`、`feature_run_dao.go`--持久层。

关注：写 API 是 producer-neutral 的；PhoenixA 不执行 Python、不解析公式。

#### 第 8 站：UI（再懂"用户看到什么"）

- `app/projects/cthulhu/src/app/features/feature-platform/feature-platform.routes.ts`--7 个页面路由。
- `app/projects/cthulhu/src/app/features/feature-platform/services/feature-platform-api.service.ts`--9 个方法（8 GET + 1 POST compute）。
- `app/projects/cthulhu/src/app/features/feature-platform/pages/manual-compute-page.component.ts`--手工触发表单。
- `app/projects/cthulhu/src/app/features/feature-platform/pages/values-page.component.ts`--值查询 + 图表。

关注：UI 只读 + compute；sync/validate/publish/backfill 没有入口（见 §1.3）。

#### 建议的"边读边跑"

```bash
# 1. 启动 PhoenixA + Artemis（当前版本）
# 2. sync 两个 smoke manifest
curl -sS -X POST http://127.0.0.1:8084/features/registry/sync -d '{"source_profile":"default","check_entrypoints":true}'
# 3. 对 constant_one 发一次 compute，拿到 run_id
# 4. 在 Cthulhu /workbench/features/runs/<run_id> 看状态时间线、RunItems、Subjects、Value 样本
# 5. 对照 feature_compute_task.py 的七阶段，看每个阶段在 Run Detail 上的体现
```

读完这 8 站，再回头看本文 §4 的 `debt_to_assets` 操作步骤，每一步该改哪个文件、平台会怎么处理，就一目了然了。

### 1.5 运行时数据流：一次 compute 走过七站

`Manifest -> Registry Sync -> Planner -> Executor -> Provider -> Writer -> Query` 这条流程其实是**两层服务 + 四个时间维度**交织出来的。

#### 两个关键区分

**两层服务**（架构设计 §5）：

- **Artemis = 计算面**（干活：解析 manifest、跑 plugin、拉数据、写值）
- **PhoenixA = 控制面 + 存储**（持有真相：Registry 表、Run 表、Value 表）

**四个时间维度**（容易混的地方）：

| 时间 | 阶段 | 频率 |
|---|---|---|
| 定义时 | Manifest（写 YAML + plugin 代码） | 每个版本写一次 |
| 发布时 | Registry Sync | 每个版本 sync + publish 一次 |
| 运行时 | Planner -> Executor -> Provider -> Writer | **每次 compute 都跑一遍** |
| 读取时 | Query | 任意时刻 |

所以 `Manifest -> Registry Sync` 是"一次定义、一次发布"，`Planner -> ... -> Writer` 是"每次算都重跑"，`Query` 是"算完随时查"。它们不是同一条时间线上的七步，而是三个阶段。

#### 全景图

```text
定义/发布时（每版本一次）：
  Git YAML ──sync──> PhoenixA Registry 表
  (Manifest)         (govern.feature_definition/version/...)

运行时（每次 compute）：
  POST /features/compute
        │
        ▼
   ┌─ Artemis ──────────────────────────────────────┐
   │ 1. Planner  ──resolve──> PhoenixA Registry  (拿到依赖图)
   │                ──create──> PhoenixA Run 表   (冻结上下文)
   │ 2. Executor ──load──> Plugin (你的 .py)
   │      └─ Plugin 调 ─> 3. Provider ──query──> PhoenixA 财务API (拿源数据)
   │ 4. Writer   ──write──> PhoenixA Value 表    (写结果)
   └────────────────────────────────────────────────┘

读取时（任意时刻）：
  Cthulhu/curl ──query──> PhoenixA Value 表 (dwd.feature_value_numeric)
```

注意：**Provider 是 Plugin 在 Executor 阶段里调用的**，不是 Executor 之后的独立步骤。线性箭头 `Executor -> Provider` 容易误导，实际是嵌套关系：`Executor 调 Plugin，Plugin 调 Provider`。

#### 跟着 `debt_to_assets` 走一遍

**① Manifest（定义时 · Artemis 仓库）** - 你写的两个文件，纯静态，还没跑任何东西：

- `config/feature_catalog/features/financial/metrics/debt_to_assets.yaml` - 说明书：code、version、entrypoint、2 个 data_field 依赖、quality 门禁
- `artemis/feature_platform/plugins/financial/metrics/debt_to_assets.py` - 执行者：`DebtToAssetsFeature` 类

此时 manifest 只存在于 Git，PhoenixA 完全不知道有这个 feature。

**② Registry Sync（发布时 · Artemis -> PhoenixA）** - `POST /features/registry/sync` 触发：

1. Artemis loader 读 `manifest.yaml` 索引 -> 加载 YAML -> schema/pydantic 校验 -> 算 checksum
2. Artemis 把 manifest 投影成 PhoenixA wire contract，调 PhoenixA `POST /api/v2/features/registry/sync`
3. PhoenixA `feature_registry_service.go`：建 `govern.feature_definition` / `feature_version`(draft) / `feature_implementation` / `feature_dependency`（把 `TOTAL_LIAB`/`TOTAL_ASSETS` 自然键五元组**解析成 `data_field_dictionary_id`** 并冻结），全图环检测
4. 调 `:publish`，v1 状态 `draft -> published`，**从此不可改**

结果：PhoenixA 持有了"debt_to_assets v1 是什么"的权威、不可变记录。后续 compute 都从这里解析版本，不再读你的 YAML。

**③ Planner（运行时 · Artemis，每次 compute）** - `POST /features/compute` 触发：

1. 从 PhoenixA Registry 解析 `debt_to_assets@1` -> 精确 `feature_version_id`
2. 递归解析依赖（本例只有 2 个 data_field 依赖，DAG 很浅），二次环检测 + 拓扑排序
3. 算 `dependency_plan_checksum`
4. 在 PhoenixA 建 `govern.feature_run` 行，**冻结**：`as_of_time`、`data_cutoff_time`、`universe_hash`、`plan_checksum`、`code_revision`、`request_fingerprint`
5. 冻结 `govern.feature_run_subject`（这批 security_id 快照），提交 ASYNC Task，返回 `202 + run_id`

关键：Run 一旦创建，上下文冻结。Task 执行前会重新 plan 并比对 checksum，不一致就 fail closed（防排队期间 Registry 漂移）。

**④ Executor（运行时 · Artemis，每个 DAG 节点）** - TaskEngine 的 `execute` 阶段，对拓扑序里每个节点（本例就 1 个）：

1. `python_executor.py` 按 entrypoint 导入 `DebtToAssetsFeature`，实例化
2. 调 `plugin.validate(...)` -> `plugin.load_inputs(ctx, provider, dependencies)`（里头调 Provider）-> `plugin.compute(ctx, inputs)` -> `plugin.validate_output(...)`
3. 平台 `output_validator.py` 再做通用校验：universe 覆盖、类型、NaN/Inf、重复、覆盖率门禁

整个过程在 daemon thread 里跑，有 `plugin_timeout_seconds` 超时保护。**plugin 拿不到数据库连接**，只能通过 provider 读数据、返回 typed output。

**⑤ Provider（运行时 · Artemis，被 plugin 调用）** - plugin 的 `load_inputs` 里对每个 data_field 依赖调 `provider.load_data_field(ctx, dep)`：

1. `providers/phoenixa.py` 调 PhoenixA `GET /api/v2/financial/amazing_data/balance_sheet?format=flat&fields=...TOTAL_LIAB&security_ids=...`
2. 分页拉完所有行
3. **PIT 权威过滤**：`available_at = actual_ann_date 否则 ann_date`，`available_at > data_cutoff_time` 的记录丢弃
4. 返回 `DataFieldBatch`（每条记录带 `security_id`/`value`/`available_at`/`reporting_period`/`metadata`）

debt_to_assets 调两次（LIAB 一次、ASSETS 一次），拿到两个 batch，在 `compute` 里按元组键对齐到同一张报表算 `liab/assets`。

**⑥ Writer（运行时 · Artemis -> PhoenixA）** - 计算和校验通过后，`storage/phoenixa_writer.py` 分批（每批 ≤5000 行）调 PhoenixA `POST /api/v2/features/runs/{run_id}/values/numeric:batch`：

1. PhoenixA 校验：Run 处于 running/validating、security 在 RunSubject 里、`source_max_available_at <= data_cutoff_time`
2. **数据库 trigger 再校验一次 cutoff**（defense-in-depth，防直接 SQL 写入）
3. 写入 `dwd.feature_value_numeric`（TimescaleDB hypertable）
4. 主键冲突且内容相同 = 幂等成功；内容不同 = 409
5. RunItem `validating -> succeeded`，Run `validating -> succeeded`

写入后值**不可改**，要修正只能创建新 Run。

**⑦ Query（读取时 · PhoenixA，任意时刻）** - 算完后 Cthulhu Values 页或 curl 直接查 PhoenixA（不经 Artemis）：

- `GET /api/v2/features/values/numeric/latest` - 最新成功物化（自动选最高 published 版本）
- `GET /api/v2/features/values/numeric/cross-section` - 某天全市场横截面
- `GET /api/v2/features/values/numeric?feature_code=...&version=1&run_id=...` - 指定 Run/版本

默认只返回 `succeeded` Run 的值；`partial/aborted` 默认隐藏。读的是 `dwd.feature_value_numeric`，和 Artemis 进程无关--所以 **Artemis 重启后值还在**。

#### 一句话串起来

> 你在 Git 写 YAML + plugin（**Manifest**）-> sync 到 PhoenixA 落库成不可变版本（**Registry Sync**）-> 每次 compute，Artemis 解析依赖图并冻结一次 Run（**Planner**），在超时保护下调你的 plugin（**Executor**），plugin 通过 provider 从 PhoenixA 拉 cutoff 前的源数据（**Provider**），算完的结果由平台写回 PhoenixA 的值表（**Writer**），之后任何时候都能从值表查（**Query**）。

定义/发布是"一次性的"，计算是"每次重跑的"，查询是"随时可读的"--这三个时间维度分开理解，整个流程就不乱了。

#### 复用边界：compute 只读 ODS+内存，不读值表

先明确一个容易混的点：**compute 过程只读 ODS（经 provider）和本 Run 内存，绝不读 `dwd.feature_value_numeric`（值表）。** 值表是 write-once-during-run、read-only-during-query--只给 Cthulhu/curl 查询和未来回测用，不喂给新计算。架构 §10.3 原文："P0/P1 不复用历史 FeatureValue 做依赖缓存，先保证正确性"。

所以你今天算 `roe_ttm`，不会去读昨天落库的 `net_income_ttm`；它会把 `net_income_ttm` 当作本 Run 的一个 RunItem 从 ODS 重新算一遍。这也意味着每次 Run 自包含：第 47 次 Run 失败不会污染第 48 次，"之前没算过 B"也不阻塞 A（B 会在 A 的 Run 里现算）。

但"每次都全重算"有一个例外，要分清两种复用：

| 复用类型 | 含义 | Phase 0-2 是否做 |
|---|---|---|
| **Value 级复用** | 算新 Run 时，读旧 Run 落库的值当输入 | ❌ 不做 |
| **Run 级复用** | 整个请求和某个已成功 Run 完全一致，直接返回那个老 Run | ✅ 做 |

关键区别：Value 级是"读旧值拼新计算"（部分复用），Run 级是"整次跳过、原样返回"（全有或全无）。**没有"读一半旧值、算一半新值"的中间态。**

##### Run 级复用怎么触发：request_fingerprint

每个 Run 创建时，PhoenixA 算一个 `request_fingerprint`（SHA-256），输入是**所有会影响计算结果**的字段：

- root feature version IDs（算哪些 `feature@version`）
- dependency plan checksum（依赖图指纹）
- universe_hash（security_ids 的 SHA-256）
- `as_of_time`、`data_cutoff_time`
- `source_profile`、`market`
- `parameters`（含调用方传的 `idempotency_key`）
- `code_revision`（Artemis 构建 commit）

**两次请求只要这些字段全一致，指纹就相同。** PhoenixA 建新 Run 前先拿指纹查已有 Run：

```text
第 1 次调用（debt_to_assets@1, 10 个证券, as_of=2026-07-18, cutoff=2026-07-18, ...）
  指纹 = SHA-256(...) = abc123...
  PhoenixA 没找到指纹 abc123 的 Run
    -> 建新 Run U1（queued），返回 202 + run_id=U1
    -> Artemis 从 ODS 全重算，写值，U1 -> succeeded

第 2 次调用，请求体一模一样
  指纹 = SHA-256(...) = abc123...（相同）
  PhoenixA 找到指纹 abc123 的 succeeded Run U1
    -> 直接返回 U1，HTTP 200, reused=true
    -> 不建新 Run、不重算、不重取 ODS、不写新值
```

第 2 次返回的就是第 1 次那个 `run_id`，整条链一个字节都没重算。这就是"跳过整次计算"，不是"读旧值拼新计算"。

##### 为什么它和 Value 级复用不是一回事

- **Run 级复用** = "你问了我昨天问的一模一样的问题，我把昨天的答案原样给你，不重新算"
- **Value 级复用** = "你在算一道**新**题，但其中有个子步骤和昨天某道题一样，我把昨天那个子步骤结果抄过来用" ← **这个平台不做**

这正是为了保证 PIT 正确：不会把旧 cutoff 下物化的值混进新 cutoff 的计算。

##### 什么时候触发复用，什么时候新建 Run

| 场景 | 指纹 | 行为 |
|---|---|---|
| 同一请求发两次（cron 重试、手抖双击） | 相同 | 复用老 Run（200, reused=true） |
| 两个并发相同请求 | 相同 | 第二个挂到正在跑的那个 Run，不重复算 |
| 次日算（as_of 变了） | 不同 | 新建 Run，全重算 |
| 换 cutoff / universe / source | 不同 | 新建 Run，全重算 |
| 发了 V2 版本 | 不同 | 新建 Run，全重算 |
| Artemis 重新构建（code_revision 变） | 不同 | 新建 Run，全重算 |
| 老 Run 是 failed/aborted | — | 不复用，可建新 attempt |
| `force=true` | — | 强制新建 Run（不复用，老 Run 和老值不覆盖，两者共存） |
| 带 `retry_of_run_id` | — | 新建 retry Run，链到老 Run |

注意：`force` 和 `retry_of_run_id` 是**控制开关**，不进指纹；`idempotency_key` 进 `parameters`、进指纹，所以调用方可以用它控制复用粒度（同 key 复用、换 key 新建）。

##### 为什么这么设计

1. **幂等**：cron 每天触发、网络抖动重试、手抖双击，都不会重复算或写重复值。
2. **安全重试**：请求失败重发，拿到同一个 run_id，不会双倍计算。
3. **并发保护**：两个相同请求并发到达，第二个挂到第一个的 Run 上，不重复算。
4. **确定性**：指纹覆盖所有影响输出的字段，"同指纹 = 同结果"成立，复用才安全。

代价是深 DAG × 大 universe × 多日期回填重算量大；架构把 Value 级复用（materialization reuse）推迟到未来，且即便做也必须 `version/as_of/cutoff/universe` 四项全一致才能复用（§10.3）。

---

## 2. 调研结论：平台现状与可用财务数据

### 2.1 Feature Platform 已就绪

- **控制面（PhoenixA）**：`govern.feature_definition/version/implementation/dependency`、`govern.feature_run/run_item/run_subject`、`dwd.feature_value_numeric`（TimescaleDB hypertable）全部落地，迁移文件 `app/projects/phoenixA/migrations/postgresql/security/0008_feature_platform.sql` 已应用。
- **执行面（Artemis）**：Manifest loader/validator/checksum、Planner（精确版本 DAG + 环检测 + 稳定拓扑序 + plan checksum）、Python Executor（daemon thread + 超时）、Output Validator、`FeatureComputeTask`（复用 `BaseTaskUnit` 七阶段）、PhoenixA provider/writer 全部就绪。
- **已有两个 smoke Feature**（`platform.security.constant_one@1`、`platform.security.datafield_pit_probe@1`）已 Published，分别验证「无依赖控制面链路」和「单 DataField + PIT 链路」。
- **多 DataField 依赖已确认可用**：`python_executor.py` 把所有 dependency snapshot 作为 list 传给 `plugin.load_inputs(ctx, provider, dependencies)`，插件对每个依赖调 `provider.load_data_field`。smoke probe 限制「恰好 1 个」只是 probe 自我约束，不是平台限制。

### 2.2 现有财务数据

财务字段字典由 `app/projects/phoenixA/migrations/postgresql/security/0004_govern_seed.sql` 灌入，源头是 `scripts/field_dictionary/amazing_data/financial_statement.fields.jsonl`。

- **当前只有一个 `contract_version = "2026-06-27"`**，`source = amazing_data`，`dataset = financial_statement`。
- 三张表字段数量：`balance_sheet` 179 个、`cashflow` 120 个、`income` 110 个。

与因子直接相关的 `is_core=TRUE` 字段节选：

| 表 (`data_type`) | `raw_field` | 中文 | 因子用途 |
|---|---|---|---|
| `income` | `NET_PRO_EXCL_MIN_INT_INC` | 净利润（不含少数股东） | ROE 分子 / 净利率分子 |
| `income` | `TOT_OPERA_REV` | 营业总收入 | 净利率分母 |
| `income` | `EBIT` / `EBITDA` | 息税前/息税折旧摊销前利润 | 盈利因子 |
| `balance_sheet` | `TOTAL_ASSETS` | 资产总计 | 资产负债率分母 / 规模 |
| `balance_sheet` | `TOTAL_LIAB` | 负债合计 | 资产负债率分子 |
| `balance_sheet` | `TOT_SHARE_EQUITY_EXCL_MIN_INT` | 股东权益（不含少数股东） | ROE 分母 |
| `balance_sheet` | `TOTAL_CUR_ASSETS` / `TOTAL_CUR_LIAB` | 流动资产/负债合计 | 流动比率 |
| `cashflow` | `NET_CASH_FLOW_OPERA_ACT` | 经营活动现金流量净额 | 现金流因子 |

### 2.3 PIT 已在 provider 层权威实现

`app/projects/artemis/artemis/feature_platform/providers/phoenixa.py`：

- `available_at = actual_ann_date 否则 ann_date`，按 `Asia/Shanghai` 当日 00:00 解释；
- `available_at > data_cutoff_time` 的记录在 Artemis 侧被丢弃；
- **不依赖 PhoenixA 的 `ann_date_before` 过滤**，因为它不看 `actual_ann_date`，不能作为 PIT 防线；
- provider 返回的每条 `DataFieldRecord` 都带 `available_at`、`reporting_period` 和 metadata（`ann_date`/`actual_ann_date`/`report_type`/`statement_code`）。

---

## 3. 选定因子与选择理由

### 3.1 选定因子

```text
financial.security.debt_to_assets@1
  = TOTAL_LIAB / TOTAL_ASSETS
  口径：data_cutoff_time 前最新已公告的合并资产负债表（snapshot，单期）
```

两个 DataField 依赖：

- `amazing_data / financial_statement / balance_sheet / TOTAL_LIAB @ 2026-06-27`
- `amazing_data / financial_statement / balance_sheet / TOTAL_ASSETS @ 2026-06-27`

`kind = metric`（Fundamental Metric，不是 factor），`category = fundamental`。

### 3.2 为什么选它，而不是 ROE 或净利率

架构设计 §19.3 给的示例链是 `net_income_ttm -> average_equity -> roe_ttm`，看上去该从 ROE 开始。但 §19.3 同时明确要求**不要直接从复合因子开始**，应按 `DataField -> Fundamental Metric -> Normalized Metric -> Financial Factor` 分层。第一个因子应是**最简单的 Fundamental Metric**，用来把平台机制跑通。

| 候选 | 依赖 | 变量类型 | 季节性 | 跨表 | 分母为零风险 | 需要 TTM/多期 | 作为「第一个」的适配度 |
|---|---|---|---|---|---|---|---|
| **资产负债率** | 2× balance_sheet | stock / stock | 无 | 否（同表） | 几乎无 | 不需要 | ★★★★★ |
| 净利率 | 2× income | flow / flow | 有（Q4 偏高） | 否 | 有（金融/准上市） | 单期可做但噪声大 | ★★★ |
| ROE TTM | income + balance_sheet | flow / stock | 有 | 是 | 有 | 需要（TTM 4 季 + 平均权益） | ★★ |

**资产负债率作为第一个因子的决定性理由**：

1. **stock/stock，无季节性**。资产负债表是时点快照，「cutoff 前最新一期」语义干净；income 是流量，单期净利率受 Q4 集中确认影响，TTM 才稳--TTM 是第二个因子该解决的问题，不该在第一个因子里混进来。
2. **单表双字段**。两个 `raw_field` 都在 `balance_sheet`，provider 调用模式与 smoke probe 最接近，只是从 1 个字段扩到 2 个字段，学习曲线平滑。
3. **分母稳健**。`TOTAL_ASSETS` 对真实上市公司几乎恒 > 0，除零/缺失分支少，能把精力放在平台机制而非边界 case。
4. **逼出核心 PIT 教学点**。stock 变量的正确选样是「`available_at <= cutoff` 的记录里选 `reporting_period` 最大者」，而 smoke probe 选的是 `max(available_at, ...)`。这两者的区别正是架构设计 §11 反复强调的「报告期 ≠ 信息可用时间」。第一个因子就把这个概念踩实。
5. **修订公告自然落位**。选样按 `(reporting_period, available_at)` 排序，同一报告期的修订记录 `available_at` 更大、自然胜出，满足「修订公告只在实际可用后替换旧记录」的硬约束。
6. **真因子语义**。资产负债率是公认的杠杆/质量因子，后续做行业中性化、winsorize、接入回测都有真实落点，不是占位。

**结论**：第一个因子做 `debt_to_assets`（Fundamental Metric）。ROE TTM 作为第二个因子，届时再引入跨表 + TTM + 平均权益的复杂度。

---

## 4. 逐步操作指南

### Step 0 - 前置确认（环境门禁）

按 Phase 1 报告 §8 和 Phase 5 验收，启动真实计算前确认：

1. PhoenixA 已启用 TimescaleDB，DBA 已建 `warm_storage` tablespace，`0008_feature_platform.sql` 已应用。
2. PhoenixA 进程是**加载了 `/api/v2/features/*` 路由的新版本**（Phase 4 报告提到 8085 上曾跑旧进程，须先重启）。
3. Artemis `engine.feature_platform.enabled=true`，source profile 指向同一 PhoenixA。
4. 已有 ≥10 个有效 `security_id`（从 `ods.security_registry` 取）。

```bash
# 快速冒烟：constant_one 能 compute 成功，说明链路 OK
curl -X POST http://<artemis>/features/compute -d '{
  "features":[{"code":"platform.security.constant_one","version":1}],
  "security_ids":[<10个id>],
  "as_of_time":"2026-07-18T15:00:00+08:00",
  "data_cutoff_time":"2026-07-18T15:00:00+08:00",
  "market":"zh_a","source_profile":"home","trigger_type":"manual"
}'
```

### Step 1 - 设计因子身份与口径

| 项 | 值 |
|---|---|
| `feature_code` | `financial.security.debt_to_assets` |
| `kind` | `metric` |
| `entity_type` | `security` |
| `value_type` | `number` |
| `unit` | `ratio` |
| `category` | `fundamental` |
| `version.number` | `1` |
| `as_of_semantics` | `snapshot`（平台 Phase 2 只支持 snapshot） |
| `missing_policy` | `explicit_missing`（平台只支持这个） |
| 公式 | `TOTAL_LIAB / TOTAL_ASSETS`，取 cutoff 前最新已公告合并报表 |
| `min_coverage_ratio` | 初次冒烟用 `0.0`，验证通过后调到 `0.90` |

**PIT 选样规则**（本因子核心，须写进 plugin 注释）：

```text
对每个 security：
  1. 仅保留 available_at <= data_cutoff_time 的记录（provider 已做）
  2. 在剩余记录里按 (reporting_period DESC, available_at DESC, statement_code, report_type)
     选唯一一行：
       - reporting_period 优先：用「cutoff 前已公告的最新报告期」
       - available_at 次之：同一报告期的修订记录自然胜出
       - statement_code 偏好合并报表('1')
  3. TOTAL_ASSETS 缺失/为 0/非有限 -> value_status=missing 或 invalid
     TOTAL_LIAB 缺失/非有限 -> missing
     两者都有限且分母 != 0 -> valid, value = liab/assets
  4. source_max_available_at = 选中行的 available_at（有 DataField 依赖，必填）
```

> **关键约束**：两个依赖（TOTAL_LIAB、TOTAL_ASSETS）分别 fetch，得到两个 `DataFieldBatch`，但它们命中**同一批物理行**（同一张资产负债表 `data_json` 里的两个字段）。因此选样**必须只看元组 `(reporting_period, available_at, statement_code, report_type)`**，不能看 value--这样两个 batch 会选中同一张报表，分子分母才匹配。这是本因子最容易写错的地方。

### Step 2 - 写 Manifest

**新文件**：`app/projects/artemis/config/feature_catalog/features/financial/metrics/debt_to_assets.yaml`

```yaml
api_version: chaos.feature/v1

feature:
  code: financial.security.debt_to_assets
  display_name: Debt-to-Assets Ratio
  description: >-
    总负债 / 总资产。取 data_cutoff_time 前最新已公告的合并资产负债表
    （snapshot，单期）。用于验证多 DataField 依赖、PIT 报告期选样与比率
    计算链路。
  kind: metric
  entity_type: security
  value_type: number
  unit: ratio
  category: fundamental
  owner: research-platform
  tags: [financial, fundamental, leverage]

version:
  number: 1
  status: draft          # 先 draft，review 后再 publish
  frequency: quarterly
  as_of_semantics: snapshot
  missing_policy: explicit_missing
  description: Initial single-period balance-sheet leverage metric.

implementation:
  kind: python
  producer_service: artemis
  backend: python
  entrypoint: artemis.feature_platform.plugins.financial.metrics.debt_to_assets:DebtToAssetsFeature
  implementation_revision: 1
  config: {}
  status: active

dependencies:
  - kind: data_field
    source: amazing_data
    dataset: financial_statement
    data_type: balance_sheet
    raw_field: TOTAL_LIAB
    contract_version: "2026-06-27"
  - kind: data_field
    source: amazing_data
    dataset: financial_statement
    data_type: balance_sheet
    raw_field: TOTAL_ASSETS
    contract_version: "2026-06-27"

materialization:
  store: numeric
  mode: snapshot

quality:
  min_coverage_ratio: 0.0   # 冒烟期；验证后调 0.90
  allow_nan: false
  allow_infinite: false
  allow_duplicates: false
```

### Step 3 - 注册到 catalog 索引

**改文件**：`app/projects/artemis/config/feature_catalog/manifest.yaml`

```yaml
api_version: chaos.feature.catalog/v1
features:
  - features/platform/constant_one.yaml
  - features/platform/constant_two.yaml
  - features/platform/datafield_pit_probe.yaml
  - features/financial/metrics/debt_to_assets.yaml   # 新增
```

> Loader 默认只读索引里显式列出的文件，不扫描目录，**不注册 = 不加载**。路径解析后必须仍在 catalog root 内，阻止 `../` 逃逸。

### Step 4 - 写 Plugin

**新文件**：`app/projects/artemis/artemis/feature_platform/plugins/financial/metrics/debt_to_assets.py`

同时确保 `plugins/financial/__init__.py`、`plugins/financial/metrics/__init__.py` 存在（空文件即可），否则 entrypoint 导入失败。

```python
from __future__ import annotations

import math
from typing import Any

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput, NumericValue
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.providers.base import DataFieldBatch

# 选样只看元组，保证两个 batch（LIAB / ASSETS）选中同一张报表
STMT_KEY = ("reporting_period", "available_at", "statement_code", "report_type")


class DebtToAssetsFeature:
    """资产负债率 = TOTAL_LIAB / TOTAL_ASSETS，cutoff 前最新已公告合并报表。"""

    EXPECTED_FIELDS = {"TOTAL_LIAB", "TOTAL_ASSETS"}

    def validate(self, definition: dict, version: dict, implementation: dict) -> None:
        if definition.get("value_type") != "number":
            raise FeaturePlatformError("INPUT_SCHEMA_INVALID", "debt_to_assets requires number value_type")

    def load_inputs(self, ctx: FeatureExecutionContext, provider, dependencies: list[dict]):
        data_fields = [d for d in dependencies if d.get("kind") == "data_field"]
        if len(data_fields) != 2:
            raise FeaturePlatformError("DEPENDENCY_REFERENCE_INVALID", "exactly two data_field deps required")
        raw_fields = {d["raw_field"] for d in data_fields}
        if raw_fields != self.EXPECTED_FIELDS:
            raise FeaturePlatformError("DEPENDENCY_REFERENCE_INVALID", f"expected {self.EXPECTED_FIELDS}")
        # 每个 dependency 各拉一次；两个都来自 balance_sheet，命中同一批物理行
        return {d["raw_field"]: provider.load_data_field(ctx, d) for d in data_fields}

    def _select_key(self, record) -> tuple:
        m = record.metadata
        # reporting_period DESC -> 字符串倒序即可（ISO 日期）
        return (
            record.reporting_period,
            record.available_at,
            str(m.get("statement_code") or ""),
            str(m.get("report_type") or ""),
        )

    def compute(self, ctx: FeatureExecutionContext, inputs: dict[str, DataFieldBatch]) -> FeatureNumericOutput:
        liab_batch = inputs["TOTAL_LIAB"]
        asset_batch = inputs["TOTAL_ASSETS"]

        def index(batch: DataFieldBatch) -> dict[int, list]:
            out: dict[int, list] = {sid: [] for sid in ctx.security_ids}
            for r in batch.records:
                out.setdefault(r.security_id, []).append(r)
            return out

        liab_by = index(liab_batch)
        asset_lookup = {(r.security_id, self._select_key(r)): r for r in asset_batch.records}

        rows: list[NumericValue] = []
        for sid in ctx.security_ids:
            liab_records = liab_by.get(sid, [])
            if not liab_records:
                rows.append(self._missing(sid, "no_balance_sheet_at_cutoff", ctx.data_cutoff_time))
                continue
            selected = max(liab_records, key=self._select_key)
            asset_record = asset_lookup.get((sid, self._select_key(selected)))
            if asset_record is None:
                # 两 batch 未对齐 -- 实现错误，fail closed
                raise FeaturePlatformError(
                    "OUTPUT_SCHEMA_INVALID",
                    f"asset record not aligned for security {sid} at {selected.reporting_period}",
                )
            liab_v = self._to_float(selected.value)
            asset_v = self._to_float(asset_record.value)
            avail = selected.available_at  # 选中报表的公告时间

            if liab_v is None or asset_v is None:
                rows.append(self._missing(sid, "source_value_missing", avail))
            elif asset_v == 0:
                rows.append(NumericValue(security_id=sid, value=None,
                    value_status="invalid",
                    quality_flags={"reason": "zero_total_assets"}, source_max_available_at=avail))
            else:
                ratio = liab_v / asset_v
                if not math.isfinite(ratio):
                    rows.append(NumericValue(security_id=sid, value=None,
                        value_status="invalid",
                        quality_flags={"reason": "ratio_not_finite"}, source_max_available_at=avail))
                else:
                    rows.append(NumericValue(security_id=sid, value=ratio,
                        value_status="valid",
                        quality_flags={"reporting_period": selected.reporting_period},
                        source_max_available_at=avail))

        return FeatureNumericOutput(feature_version_id=ctx.feature_version_id,
                                    observed_at=ctx.as_of_time, rows=rows)

    def validate_output(self, ctx: FeatureExecutionContext, output: FeatureNumericOutput) -> None:
        if len(output.rows) != len(ctx.security_ids):
            raise FeaturePlatformError("OUTPUT_SCHEMA_INVALID", "one output per RunSubject required")
        # 有 DataField 依赖，每条 valid/missing/invalid 都必须有 source_max_available_at
        for row in output.rows:
            if row.source_max_available_at is None:
                raise FeaturePlatformError("OUTPUT_SCHEMA_INVALID",
                    f"security {row.security_id} missing source_max_available_at")

    @staticmethod
    def _to_float(v: Any) -> float | None:
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    @staticmethod
    def _missing(sid: int, reason: str, avail) -> NumericValue:
        return NumericValue(security_id=sid, value=None, value_status="missing",
            quality_flags={"reason": reason}, source_max_available_at=avail)
```

> 关键点：`_select_key` 只用元组字段，所以 LIAB batch 和 ASSETS batch 对同一张报表算出同一 key，`asset_lookup` 一定能命中。这保证了分子分母来自同一期报表。

### Step 5 - 写测试

**改文件**：`app/projects/artemis/tests/test_feature_platform_manifests.py` 和 `test_feature_platform_planning_execution.py`，覆盖开发者指南 §10 的最低测试矩阵：

1. **Manifest schema**：unknown field / 敏感 key / 坏 entrypoint 被拒；canonical checksum 稳定。
2. **依赖**：2 个 data_field 依赖精确解析到 `balance_sheet` 的两个字段，`contract_version=2026-06-27` 冻结。
3. **PIT fixture（核心）**：构造 cutoff 前公告、cutoff 后公告、修订公告三类记录，断言：
   - cutoff 后公告的记录不进入输入；
   - 选中 cutoff 前最新 reporting_period；
   - 修订公告可用后替换旧值；
   - `source_max_available_at == 选中行的 available_at`，且 `<= data_cutoff_time`。
4. **计算**：正常 valid、`TOTAL_ASSETS=0` -> invalid、字段缺失 -> missing、missing 不填 0。
5. **负例**：人工构造 `source_max_available_at > data_cutoff_time` 的写请求 -> PhoenixA 返回 `DATA_CUTOFF_VIOLATION`。

PIT fixture 可参考现有 `datafield_pit_probe` 的测试（Phase 2 报告 §6 描述了 cutoff 前/cutoff 后/修订三类记录的构造）。

### Step 6 - 本地 validate + 定向测试（只能 curl/CLI）

> 这一步没有 UI，因为 manifest 校验是开发/CI 动作（见 §1.3）。

```bash
cd app/projects/artemis
PYTHONPATH=. python -m pytest -q \
  tests/test_feature_platform_openapi.py \
  tests/test_feature_platform_manifests.py \
  tests/test_feature_platform_planning_execution.py \
  tests/test_feature_platform_service_task.py

# 离线 validate（不发布），确认 checksum 稳定、entrypoint 可导入
curl -X POST http://<artemis>/features/manifests/validate \
  -d '{"paths":["features/financial/metrics/debt_to_assets.yaml"]}'
```

PhoenixA 门禁：

```bash
cd app/projects/phoenixA
go test ./...
go vet ./...
python scripts/verify_openapi_routes.py
```

### Step 7 - Sync Draft -> review -> Publish（只能 curl）

> 这一步没有 UI：registry sync 和 publish 都是版本治理/运维动作，Cthulhu 不提供入口（见 §1.3）。

```bash
# 1. Sync draft 到 PhoenixA
curl -X POST http://<artemis>/features/registry/sync \
  -d '{"paths":["features/financial/metrics/debt_to_assets.yaml"]}'

# 2. 查 lineage / availability，确认两个 data_field 依赖都解析到 dictionary ID
#    （lineage / availability 查询可以在 Cthulhu /workbench/features/lineage 看）
curl http://<phoenixa>/api/v2/features/lineage/financial.security.debt_to_assets
curl http://<phoenixa>/api/v2/features/availability/financial.security.debt_to_assets

# 3. Code review（业务定义、PIT 口径、质量阈值）

# 4. 发布
curl -X POST http://<phoenixa>/api/v2/features/definitions/financial.security.debt_to_assets/versions/1:publish

# 5. 再 sync 一次，应返回 unchanged
```

> Published 后不可改。要改公式/依赖/口径 -> 发 V2，废弃 V1。

### Step 8 - 小 universe compute（可在 UI 或 curl 做）

> **可以在 Cthulhu 做了**：`/workbench/features/compute` 页有完整表单（feature / version / source / market / as-of / cutoff / security_ids / idempotency / retry / force）。选完 feature 会自动带出最新 published version，提交后显示 run_id 和跳转 Run Detail 的链接。下面 curl 等价：

```bash
curl -X POST http://<artemis>/features/compute -d '{
  "features":[{"code":"financial.security.debt_to_assets","version":1}],
  "security_ids":[<10个id>],
  "as_of_time":"2026-07-18T15:00:00+08:00",
  "data_cutoff_time":"2026-07-18T15:00:00+08:00",
  "market":"zh_a","source_profile":"home","trigger_type":"manual"
}'
# 202 Accepted + run_id；在 UI /workbench/features/runs/<run_id> 轮询到 succeeded
```

### Step 9 - 查询验证（可在 UI 或 curl 做）

> **可以在 Cthulhu 做了**：`/workbench/features/values` 页可按 feature/version/run/security/时间过滤，自带横截面柱状图和时序折线图。下面 curl 等价：

```bash
# latest 成功物化
curl "http://<phoenixa>/api/v2/features/values/numeric/latest?feature_code=financial.security.debt_to_assets&security_ids=<ids>"

# 横截面
curl "http://<phoenixa>/api/v2/features/values/numeric/cross-section?feature_code=financial.security.debt_to_assets&as_of_time=2026-07-18T15:00:00+08:00"
```

人工核对几只票：`TOTAL_LIAB/TOTAL_ASSETS` 是否合理（0~1 之间，金融股偏高），`source_max_available_at` 是否 ≤ cutoff、是否是真实公告日。Run Detail 页的 Numeric Value Sample（前 20 条）和 RunItems 质量计数可直接看。

### Step 10 - 回填 + 调质量门禁（只能 curl）

> BackfillJob 创建没有 UI（见 §1.3），只能 curl。

1. 把 `min_coverage_ratio` 调到业务合理值（如 0.90），发 V2（因为 V1 已 Published）。
2. 用 BackfillJob 做历史回填（`step=explicit` + 冻结日期列表，因为 Phase 1 还没有受治理交易日历，`calendar_code` 非空会 422）：

   ```bash
   curl -X POST http://<phoenixa>/api/v2/features/backfills \
     -d '{...,"step":"explicit","explicit_as_of_times":[...]}'
   ```

3. 验证 V1/V2 共存、latest 返回 V2、显式查 V1 仍可读历史（在 UI Values 页切换 version）。
4. 重启 Artemis/PhoenixA，确认 Run/Value 不丢（在 UI Runs/Run Detail 页复查）。

---

## 5. 关键风险与 PIT 注意点

1. **选样别用 value**。两个 data_field 依赖分两次 fetch，必须靠元组键对齐到同一张报表，否则分子分母跨期。
2. **`source_max_available_at` 必填且 ≤ cutoff**。有 DataField 依赖的 Feature，每行（含 missing/invalid）都要带；PhoenixA Service 层和数据库 trigger 双重拒绝越界值（`DATA_CUTOFF_VIOLATION`）。
3. **missing 不能填 0**。`value_status=missing` 时 `value` 必须 null，原因写进 `quality_flags`。
4. **不要用 `ann_date_before` 当 PIT 防线**。PhoenixA 的该过滤只看 `ann_date`，不看 `actual_ann_date`；Artemis provider 已做权威过滤，插件直接用 provider 返回的 `available_at` 即可。
5. **Published 不可改**。冒烟期 `status: draft`，验证通过再 publish；之后任何改动都发新版本。
6. **`min_coverage_ratio` 是硬门禁**，不达标 RunItem 直接 failed。冒烟先用 0.0，别让覆盖率门禁掩盖链路 bug。
7. **code_revision**。本地 dirty worktree 会标 `-dirty`，结果不可作为正式 materialization。
8. **NaN/Inf 不得写入**。平台 Output Validator 会拦，插件内也应在写 NumericValue 前判断 `math.isfinite`。

---

## 6. 后续演进路径

1. **第二个因子：ROE TTM**。引入跨表（income + balance_sheet）、TTM 4 季滚动、平均权益，并把 `net_income_ttm`、`average_equity` 拆成独立 `metric`，ROE 作为 `factor` 依赖它们--这条链会**首次测试 feature->feature 依赖的 Planner DAG 路径**（现有 smoke 都没覆盖）。
2. **标准化层**：`roe_winsorized` / `roe_industry_zscore`（依赖行业分类 `dwd.taxonomy_category_derived_flags`）。
3. **回测锁定**：用 BackfillJob 冻结历史截面，供后续回测引用完全相同的证券集与版本。

按架构设计 §19.5，Financial Feature Pack V1 的完整设计（因子清单、每个 DataField contract、PIT/TTM 算法、行业适用范围、标准化口径、质量规则、回填范围、分析和回测方案）应在平台验收后单独成文。本文只覆盖其中第一个因子的落地，是 V1 的起点而非完整 V1 设计。

---

## 7. 评审检查表

开工与发布前逐项确认：

- [ ] `feature_code` 和业务定义稳定且唯一，不与现有 code 冲突。
- [ ] Manifest 在 `manifest.yaml` 注册，路径在 catalog root 内。
- [ ] 两个 data_field 依赖都精确到 `source/dataset/data_type/raw_field/contract_version=2026-06-27`。
- [ ] provider 执行 availability cutoff（已由平台 provider 保证）。
- [ ] 选样只看元组键，两个 batch 对齐到同一张报表。
- [ ] 输出覆盖冻结 universe，missing 不填 0，每行带 `source_max_available_at`。
- [ ] `min_coverage_ratio` 有业务依据（冒烟期 0.0，正式 0.90）。
- [ ] parameters/config/log 不含敏感信息。
- [ ] 计算确定、可重试、可复现。
- [ ] PIT fixture 覆盖 cutoff 前/cutoff 后/修订公告三类。
- [ ] OpenAPI、测试、运维说明同步。
- [ ] 已在当前 PhoenixA/Artemis 版本上跑通 Sync -> Compute -> Persist -> Query -> Restart E2E。
