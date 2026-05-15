# Factor Engine × PhoenixA 后续复核与修复报告

日期：2026-05-15

范围：
- `app/projects/artemis/artemis/engines/factor_engine/`
- `app/projects/artemis/artemis/services/factor_service.py`
- `app/projects/artemis/artemis/core/clients/phoenixA_client.py`
- `app/projects/artemis/tests/`
- `app/projects/cthulhu/src/app/features/workbench/`
- `app/projects/phoenixA/internal/model/taxonomy.go`
- `app/projects/phoenixA/internal/dao/taxonomy_dao.go`
- `app/projects/phoenixA/internal/service/catalog_service.go`
- `app/projects/phoenixA/docs/api_biz_data_description/`

---

## 1. 本轮结论摘要

本轮在阅读以下文档并复核 Artemis / PhoenixA 实现后，对 factor engine 进行了 follow-up review 与修复：

- `2026-05-14 [REVIEW] FACTOR_ENGINE_PHOENIXA_INTEGRATION_AND_FACTOR_MANAGEMENT.md`
- `2026-05-08 [IMPLEMENTING] FEATURE_FUNDAMENTAL_FACTOR_ENGINE.md`

结论：

1. **2026-05-14 文档中提到的多数 contract drift 已经在代码中被修复**，包括：
   - 日期/报告期归一化
   - `reporting_period` / `report_period` 兼容
   - bars 字段归一化冲突
   - DPS/Dividend Yield 改为来自 `corporate_action/dividend`
   - PEG 实现
   - ranking 使用 `higher_is_better`
   - `exclude_financial=True` 真正执行

2. **本轮发现并修复了 4 个高价值问题**：
   - industry map 子集缓存污染全量缓存
   - `run_incremental()` 收尾日志变量错误
   - `get_active_symbols(as_of_date)` 之前没有真正按 as-of 过滤
   - `/factors/availability` 之前把“不可达/未知”误报成“missing”，且不检查 required fields

3. **PhoenixA 新增的 `TaxonomyCategoryDerivedFlags` feature 已经被 factor engine 正确接入并使用**：
   - `phoenixA` 侧：`taxonomy_security_map + taxonomy_category + taxonomy_category_derived_flags` 汇总到 `GET /api/v2/taxonomy/by_security/{symbol}`
   - `Artemis provider`：读取响应中的 `derived_flags`
   - `FactorPipeline`：在缺失 `comp_type_code` 时回退使用 `derived_flags.financial_sector` 做金融行业排除判断

4. **Availability 页面之前出现“Source Readiness 全 missing / Factor Availability Live 全 missing 但 Expected=ready”**，根因不是单一数据问题，而是：
   - `Expected` 来自静态 factor catalog，是“理论可算性”
   - `Live` 来自运行态 PhoenixA capabilities，是“当前环境可达 + 当前数据供给”
   - 原实现把“PhoenixA capabilities 不可达 / 空 payload / 不可信”全部压扁成了 `missing`
   - 原实现也只检查 source，不检查 required fields，导致另一类误报：source ready 但字段不够时仍报 `available`
   - **另外一个明确 root cause 是：Cthulhu `Factor Engine` 页面此前没有传递 Workbench 已选的 `selectedSource`，因此经常默认打到 `relx` / 当前默认源，而不是用户以为的 `home` / `production` 环境**

本轮已把这两类问题拆开：
- `unknown`：capabilities 不可达 / 空 payload / 无法可信判断
- `missing`：已确认缺 source / 缺 field
- `partial`：部分满足，部分缺失
- `available`：当前信息下可算

---

## 2. 文档与实现对齐结果

### 2.1 已对齐/基本对齐

- PIT 日期与报告期归一化：`normalize_date()` / `normalize_period()`
- 财务数据直接使用 PhoenixA canonical 字段名，不再依赖历史别名
- `bars` 查询使用 `normalize_for_cache=False`，provider 读取 `trade_date`
- `dividend_yield` / `dps` 使用 `corporate_action.dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH`
- `market_adjust_policy.adjust` 由 factor catalog 驱动
- factor catalog 已覆盖全部 39 个注册因子
- `snapshot meta` 输出 `reporting_period` / `latest_ann_date` / `freshness` / `company_kind` / `missing_reasons`

### 2.2 仍然存在的结构性缺口（本轮未落地）

- `FactorStore` 仍是内存存储，PhoenixA 侧目前 workspace 中尚未见到实际 `factor snapshot / rank` controller + route + persistence 实现
- 因此 `compute_full` / `snapshot` / `ranking` 仍属于 Artemis 进程内能力，不是跨实例持久化能力

这项属于**设计缺口**，不是本轮小修能闭环的问题；需要 PhoenixA 先落因子 snapshot API 和表结构。

---

## 3. 本轮发现并修复的问题

### 3.1 修复：industry map 子集缓存污染全量缓存

**问题现象**
- 先请求 `get_industry_map(..., symbols=[...])`
- 再请求 `get_industry_map(..., symbols=None)`
- 原实现会把子集缓存误当成全量缓存返回

**影响**
- 全量 pipeline 会拿到不完整行业映射
- 行业标准化 / 行业上下文 / 金融行业排除都会受影响

**修复方式**
- 全量 industry map cache 与 per-symbol context cache 分离
- 子集请求只缓存 per-symbol context，不再污染 full-map cache
- 全量请求会优先复用已有 per-symbol cache，只补查缺失 symbol

**修复文件**
- `artemis/engines/factor_engine/providers/phoenixa_provider.py`

---

### 3.2 修复：`run_incremental()` 收尾日志路径错误

**问题现象**
- `run_incremental()` 末尾日志引用了不存在的 `skipped_symbols`
- 增量计算主体可能已完成，但在收尾日志时报错

**修复方式**
- 移除无意义的 `skipped_symbols` 统计
- 保留 `failed_symbols`

**修复文件**
- `artemis/engines/factor_engine/pipeline.py`

---

### 3.3 修复：`get_active_symbols(as_of_date)` 以前没真正使用 `as_of_date`

**问题现象**
- provider 之前虽然接收 `as_of_date`，但没有按日期过滤证券池
- 历史重算 / 回测会有 survivorship bias 风险

**修复方式**
- `PhoenixAClient.get_securities()` 保留 `status / list_date / delist_date`
- provider 按 `list_date / delist_date` 做 as-of 过滤

**当前语义**
- `list_date > as_of_date` → 排除
- `delist_date < as_of_date` → 排除

**说明**
- 这个修复成立的前提是 PhoenixA `security_registry` 中 `list_date / delist_date` 维护正确
- 若未来要做到更严格的 PIT 证券池，最好在 PhoenixA 侧增加显式 `as_of_date` 查询参数

**修复文件**
- `artemis/core/clients/phoenixA_client.py`
- `artemis/engines/factor_engine/providers/phoenixa_provider.py`

---

### 3.4 修复：Availability 把 unknown / unreachable 全压成 missing，且不检查 required fields

**问题现象 A：误报 missing**
- PhoenixA capabilities endpoint 不可达
- 或返回空 payload / 不可信 payload
- 原实现仍把所有 source 标成 missing

**问题现象 B：误报 available**
- source 在 capabilities 中存在
- 但关键 field 不在已知输出字段中
- 原实现仍把因子标成 `available`

**修复方式**
- 引入 source readiness `status`：`ready / empty / missing / unknown`
- `capability_source` 改为：
  - `phoenixA_catalog`
  - `phoenixA_catalog_empty`
  - `unavailable`
- availability 现在同时检查：
  - required sources
  - required fields
- 对 `financial.*.data_json.*` / `corporate_action.*.data_json.*`：
  - 若 capabilities 至少声明 `data_json`，记为结构可用
  - 若未声明 `data_json`，记为缺字段
  - 若只知道 `data_json` 而不知道具体 key，记录 `field_level_unverified:*`

**修复文件**
- `artemis/services/factor_service.py`
- `cthulhu/src/app/features/workbench/models/factor.models.ts`
- `cthulhu/src/app/features/workbench/pages/factor-engine.page.ts`

---

### 3.5 修复：Factor Engine 页面之前没有使用 Workbench 的 selected source

**问题现象**
- Workbench 全局有 source 选择（`relx / home / production`）
- 但 `Factor Engine` 页面之前没有把 selected source 传给 Artemis `/factors/*` 接口
- 所以 Availability / Compute / Snapshot / Ranking 都会默认走 Artemis 当前默认源

**影响**
- 用户以为自己在看 `home` 或 `production` 环境
- 实际请求仍然打在默认 `relx`
- 于是会出现“另一个环境明明有数据，但这里仍显示 missing”的假象

**修复方式**
- Artemis `factor_routes.py` 与 `factor_service.py` 全链路增加可选 `source` 参数
- `factor_service` 改为按 source 维度维护独立 runtime（store/provider/pipeline）
- Cthulhu `Factor Engine` 页面读取 `WorkbenchStore.selectedSource()`，并把该 source 传给：
  - `/factors/availability`
  - `/factors/compute/full`
  - `/factors/compute/incremental`
  - `/factors/snapshot`
  - `/factors/rank`

**修复文件**
- `artemis/api/http_gateway/factor_routes.py`
- `artemis/services/factor_service.py`
- `cthulhu/src/app/features/workbench/services/factor.service.ts`
- `cthulhu/src/app/features/workbench/pages/factor-engine.page.ts`

---

## 4. `TaxonomyCategoryDerivedFlags` 新 feature 是否被正确使用？

### 4.1 PhoenixA 侧情况

已确认：
- `phoenixA/internal/model/taxonomy.go` 中已新增：
  - `TaxonomyCategoryDerivedFlags`
  - `TaxonomySecurityMapWithDetail.DerivedFlags map[string]bool`
- `phoenixA/internal/dao/taxonomy_dao.go` 中：
  - `ListMappingsBySymbol()` 会读取 `loadDerivedFlags()`
  - `detail.DerivedFlags = deriveCategoryFlags(...)`
- `phoenixA/internal/dao/taxonomy_dao_test.go` 中已有测试覆盖：
  - `financial_sector`
  - persisted derived flags 优先级
  - attrs_json / ancestor 推导逻辑

### 4.2 Artemis 侧使用链路

已确认 factor engine 当前使用链路如下：

1. `PhoenixAClient.get_taxonomy_by_security(symbol)`
2. `PhoenixADataProvider._match_industry_mapping()`
   - 读取 `canonical_*`
   - 读取 `derived_flags`
3. `PhoenixADataProvider.get_industry_context()`
4. `FactorPipeline._financial_company_kind()`
   - 优先使用财报 `comp_type_code`
   - 若缺失，则回退到 `industry_context.derived_flags.financial_sector`
5. `FactorPipeline._apply_factor_policies()`
   - 对 `exclude_financial=True` 的因子置空

### 4.3 结论

**是的，当前 factor engine 已经顺利且正确使用了这个新 feature。**

并且实现策略是合理的：
- **主判断信号**：`comp_type_code`
- **回退判断信号**：`derived_flags.financial_sector`

这是比以前靠 `industry_code` 前缀猜测更稳的做法。

---

## 5. 为什么你会看到：Expected=ready，但 Live=missing？

这是因为两个状态来自**两个不同层级**：

### 5.1 Expected
来自静态 factor catalog：
- `config/factor_catalog/manifest.yaml`
- `config/factor_catalog/factors/*.yaml`

它回答的问题是：
> **“按设计，这个因子理论上需要什么？如果 PhoenixA 供给正常，它应不应该可算？”**

所以很多基础因子会显示 `ready`。

### 5.2 Live
来自运行态 `GET /factors/availability`，背后依赖：
- Artemis 调 PhoenixA `/api/v2/catalog/capabilities`
- PhoenixA 返回当前环境的表/字段/数据源供给信息

它回答的问题是：
> **“当前这个环境里，PhoenixA 能不能证明这些 source / field 真的可用？”**

### 5.3 原先为什么会误导
原实现里：
- PhoenixA 不可达
- capabilities 空 payload
- parser 没识别到 table

这些情况都会被压成 `missing`。

所以你看到：
- `Expected = ready`
- `Live = missing`

其实有两种完全不同的原因：
1. **真的没数据**
2. **根本没拿到可信的 runtime capability 信息**

原先 UI 无法区分。

### 5.4 本轮修复后语义
现在应该理解为：
- `Expected = ready`：理论上该因子设计上可算
- `Live = available`：当前环境确认可算
- `Live = partial`：当前环境只满足一部分 source/field
- `Live = missing`：当前环境确认缺 source/field
- `Live = unknown`：当前环境下无法可信判断（PhoenixA 不可达 / capabilities 空 / 不可信）

所以：
- **ready + unknown** → 更像“设计上可以，但当前环境还没拿到可信 runtime 证据”
- **ready + missing** → 更像“设计上可以，但当前环境确实缺数据/字段”

---

## 6. 为什么另一个环境明明有数据，Source Readiness 还是 missing？

从代码链路看，最常见的原因有 4 类：

### 6.1 Artemis 连的不是你以为的那个 PhoenixA
`factor_service` 是通过 Artemis 配置里的 `dept_services.phoenixA` 连 PhoenixA 的。

如果：
- Cthulhu 指到了某个 Artemis
- 但那个 Artemis 的 `config.yaml` / `config-home.yaml` / `config-production.yaml` 指向了另一个 PhoenixA

那你看到的 Availability 就不是你“以为有数据的那个环境”。

### 6.2 PhoenixA `/api/v2/catalog/capabilities` 自己不可达 / 异常 / 返回空 payload
这种情况下原来会显示成 `missing`。
现在修复后应显示成：
- `capability_source = unavailable`
- source readiness = `unknown`
- factor live status = `unknown`

### 6.0 实际上此前还有一个更直接的前端原因

本轮已经确认：
- `WorkbenchStore` 内部维护了 `selectedSource`
- 但 `Factor Engine` 页面此前没用它
- 因此即使 Workbench 其它页面已经切到了 `home` / `production`，Factor Engine 仍然会默认请求 `relx`

这就是你观察到“另一个环境有数据，但 Availability 仍然显示 missing”的一个非常高概率根因。

### 6.3 PhoenixA 有原始表数据，但 capabilities payload 没把对应表/字段暴露出来
例如：
- table exists
- but capability metadata incomplete

这会导致 `Expected` 是 ready，但 `Live` 不一定能升到 available。

### 6.4 之前 UI 只看 `available: boolean`，没有显示 richer status
这也是为什么以前看起来“全 missing”特别误导。
本轮已在 Cthulhu 页面补成：
- `ready`
- `empty`
- `missing`
- `unknown`
- 并显示 `capability_error`

---

## 7. 本轮改动文件

### Artemis
- `artemis/core/clients/phoenixA_client.py`
- `artemis/engines/factor_engine/providers/phoenixa_provider.py`
- `artemis/engines/factor_engine/pipeline.py`
- `artemis/services/factor_service.py`
- `tests/test_phoenixa_factor_provider.py`
- `tests/test_factor_engine.py`
- `tests/test_factor_availability.py`

### Cthulhu
- `src/app/features/workbench/models/factor.models.ts`
- `src/app/features/workbench/pages/factor-engine.page.ts`

### 文档
- 本报告文件

---

## 8. 回归验证

本轮已执行：

```powershell
Set-Location "C:\Users\gaoc3\projects\chaos\app\projects\artemis"
python -u -m pytest tests/test_factor_engine.py tests/test_phoenixa_factor_provider.py tests/test_factor_availability.py -q
```

结果：
- **116 passed**

额外验证：
- 复现并确认修复了 subset/full industry cache bug
- 验证 availability 可将 unreachable 标成 `unknown` 而不是 `missing`
- 验证缺 `data_json` 时 `dividend_yield` 会被标为 `partial` 而不是 `available`

---

## 9. 后续建议

### P0
1. 在目标环境直接抓一次：
   - Artemis `/factors/availability`
   - PhoenixA `/api/v2/catalog/capabilities`
   对比确认到底是“连错环境”还是“capabilities metadata 空/坏”。

2. 在 Cthulhu 页面观察修复后的状态：
   - 若还是 `unknown`，优先查连通性与配置
   - 若变成 `partial/missing`，再查具体 source/field

### P1
3. PhoenixA 增强 `security_registry` / `/api/v2/securities`：
   - 支持显式 `as_of_date`
   - 在服务端完成 active universe PIT 过滤

4. PhoenixA 落地因子 snapshot / rank API 与表结构
   - Artemis `FactorStore` 才能真正从内存切换到平台级持久化

### P2
5. 将 capabilities 扩展为可选输出 JSONB key 级别 schema（而不只是 `data_json` 顶层）
   - 能让 `availability` 从“结构可验证”提升到“字段级可验证”

---

## 10. 最终判断

### 当前状态
- 设计方向：**正确**
- 代码稳定性：**比 review 前明显更稳**
- 平台化成熟度：**还差 factor persistence 这一块 PhoenixA backend 闭环**

### 风险等级
- 已修的高优先级 runtime bug：**已关闭**
- PhoenixA derived flags 接入：**已确认正确使用**
- Availability 误导性显示：**已修正语义和 UI 展示**
- 因子快照持久化：**仍是后续平台化任务**


