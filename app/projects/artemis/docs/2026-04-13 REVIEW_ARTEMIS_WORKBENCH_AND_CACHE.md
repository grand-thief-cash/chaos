# Artemis Review — Workbench / Config / Cache / Data Dimensions

> 日期: 2026-04-13
> 范围: `artemis/` + 关联 `cthulhu/workbench`
> 结论: **整体方向是对的，但目前存在几个关键的架构断点和一些会在真实使用中暴露的逻辑缺口。**

---

## 1. 我这次 review 的范围

我重点对照了以下内容：

- 设计文档
  - `docs/2026-04-02_0 FEATURE_STRATEGY_RESEARCH_WORKBENCH.md`
  - `docs/2026-04-07 FEATURE_WORKBENCH_ENV_SWITCHING.md`
  - `docs/2026-04-11 FEATURE_CACHE_ENGINE.md`
  - `docs/2026-04-11 FEATURE_WORKBENCH_DATA_DIMENSION_SELECTION.md`
- 后端实现
  - `artemis/models/configs.py`
  - `artemis/core/config_manager.py`
  - `artemis/api/http_gateway/workbench_routes.py`
  - `artemis/services/workbench/market_data.py`
  - `artemis/services/workbench/backtest.py`
  - `artemis/core/clients/phoenixA_client.py`
  - `artemis/engines/cache_engine/*`
- 前端实现
  - `cthulhu/src/app/features/workbench/**/*`
- 测试
  - `tests/test_cache_engine.py`
  - `tests/test_partition.py`
  - `tests/test_storage.py`
  - `tests/test_compaction.py`

---

## 2. 总体评价

### 做得比较好的地方

1. **Workbench 直接调用 strategy_engine 的分层是对的**  
   这条边界比走 `task_engine` 更适合交互式研发场景。

2. **CacheEngine 的目录维度设计是合理的**  
   `asset_type / market / period / adjust / symbol / partition` 这种分层，可读性和扩展性都不错。

3. **配置模型已经把 `data_options` 放在顶层**  
   这点和文档一致，避免了把 UI 选项耦合到 engine 配置里。

4. **前端已经把 Source 和维度选择器做出来了**  
   从落地速度看，后端/前端联动已经进入可试用状态，不是停留在设计阶段。

5. **cache 的单元测试基础不错**  
   `partition/storage/compaction/cache_engine` 已经有较大体量测试，这是当前代码库里质量相对靠前的一块。

---

## 3. 关键问题清单

下面按优先级拆。

### P0-1. `asset_type/market` 只进入了 cache key，没有真正进入上游数据获取语义

**现象**

- `market_data.get_market_bars()` 已经接收 `asset_type` / `market`
- 但 `_fetcher()` 最终调用的是 `PhoenixAClient.get_strategy_market_bars(...)`
- 而 `PhoenixAClient.get_strategy_market_bars()` 仍然固定访问：
  - 路径：`/api/v1/stock/hist/get_data`
  - 参数：`code/start_date/end_date/period/adjust`
- 没有把 `asset_type` / `market` 传给 PhoenixA，也没有 provider 分发逻辑

**影响**

- `stock` 以外的维度目前只是“UI 和 cache 目录可选”，不是完整的数据域能力
- 文档里已经声明支持 `index`，但当前实现没有 index 专属上游接口
- 会导致：
  - cache 层把 `index` 和 `stock` 分开存
  - 但回源层仍然用 stock API 拉数据
  - 这在语义上是断裂的

**结论**

这是这次 review 里最核心的架构问题。  
**当前系统本质上还是“stock-hist workbench”，而不是通用 market-data workbench”。**

---

### P0-2. `index` 场景下 `adjust` 被前端置空，但后端/缓存路径没有定义“空 adjust”的规范

**现象**

- 文档要求：`index` 不显示 adjust 选择器
- 前端实现：切换到 `index` 时会把 `selectedAdjust` 设为 `''`
- 但 cache 目录设计仍然固定包含 `adjust` 这一层：
  - `asset_type/market/period/adjust/symbol/...`
- 后端对空 adjust 没有 canonical 处理

**影响**

- 空字符串会让 cache 路径层级和文档预期不一致
- `compact_all()` 当前还假设路径固定 6 段（含 adjust）
- 后续再引入更多 asset_type 时，这个问题会放大

**建议**

二选一，必须统一：

1. **保留 adjust 作为 canonical 维度**：即使 `index` 不展示，也在后端归一化成固定值，例如 `nf`
2. **让 adjust 变成可选维度**：cache key/path、API model、resolver 全部升级成可选

当前更推荐方案 1，改动更小，也更稳定。

---

### P0-3. cache 有“partial hit 误判完整命中”的逻辑漏洞

**现象**

之前 `CacheEngine.get()` 的逻辑是：

- 只要 `resolve_range()` 返回了任意 base 文件
- 就直接把它当 cache hit 读出来返回

这会导致跨分区查询时：

- 例如 2024 已缓存，2025 未缓存
- 查询 `2024-12 ~ 2025-01`
- 系统会错误返回只有 2024 的数据，不回源补 2025

**影响**

这不是性能问题，是**结果错误问题**。

**处理**

我已经顺手修了这点，并新增了测试：

- 修改：`artemis/engines/cache_engine/cache_engine.py`
- 新增测试：`tests/test_cache_engine_partial_miss.py`

当前行为改成：**只有请求覆盖的所有分区都存在 base 文件时，才视为完整 cache hit。**

---

### P1-1. ConfigManager 的 override merge 是浅合并，容易把嵌套配置“半覆盖成空”

**现象**

原实现：

```python
merged = {**base_cfg, **override_cfg}
```

这意味着：

- 顶层 `server` 如果 override 只写 `port`
- 整个 `server` dict 都会被替换
- 其余 `host/access_log` 只能依赖 Pydantic 默认值，不再继承 base config

对 `data_options` 这种嵌套 dict 更危险：

- override 只覆盖 `periods`
- `asset_types/markets/adjust_rules` 会直接丢失

**影响**

- 配置覆盖语义和人类直觉不一致
- 隐性 bug 很难排查
- 对环境切换文档里强调的多套 config 尤其危险

**处理**

我已经改成了递归 merge，并补了测试：

- 修改：`artemis/core/config_manager.py`
- 新增测试：`tests/test_config_manager.py`

---

### P1-2. Config reload 时 `_data_sources` 没清空，重新初始化后可能拿到旧扫描结果

**现象**

`ConfigManager._data_sources` 是缓存的；但 `init_config(..., force=True)` 重新加载时，之前没有显式清空它。

**影响**

- 在测试/热切换/重载场景下，`available_sources()` 可能返回旧目录扫描结果
- 行为会和当前加载的 config 不一致

**处理**

我也一并修了，并在 `tests/test_config_manager.py` 里加了覆盖。

---

### P1-3. 文档要求 `period` 统一，代码仍以 `timeframe` 为主，接口契约存在漂移

**现象**

设计文档 `2026-04-11 FEATURE_WORKBENCH_DATA_DIMENSION_SELECTION.md` 里已经明确建议：

- API 参数主名统一为 `period`
- `timeframe` 仅保留 alias 兼容

但当前实现仍然是：

- 路由：`GET /workbench/market-data?timeframe=...`
- model：`IndicatorsRequest.timeframe`
- 响应：`timeframe`
- 前端字段：`selectedPeriod -> timeframe`

**影响**

- 文档、cache 语义、API 语义不统一
- 后面继续扩展时，`period/timeframe` 双命名会越来越乱

**建议**

尽快做一次 contract stabilization：

- 输入层支持 `period` 为标准字段
- `timeframe` 做 alias
- service 内部统一只使用 `period`
- 响应里也补 `period`

---

### P1-4. Workbench data options 是“全局静态配置”，但设计原则又说“维度依附于 source”

**现象**

当前：

- `GET /workbench/data-options` 直接返回顶层 `cfg.data_options`
- 与 source 无关

但设计文档第 2 节又写了：

- “Source 保留：数据维度依附于数据源，先选 Source 再选维度”

**问题本质**

现在的实现实际表达的是：

- **Source 影响后端 endpoint**
- **Data options 是全局静态 UI 配置**

这两件事都可以成立，但它们不是“维度依附于 source”。

**建议**

需要明确二选一：

1. **全局维度模式**：所有 source 共用一套 data options（当前实现）
2. **source-aware 维度模式**：`GET /workbench/data-options?source=...` 返回不同选项

如果你未来确定 `home/production` 支持集不同，那当前模型需要升级。

---

### P1-5. PhoenixAClient 没有分页/分段拉取能力，长区间分钟线存在截断风险

**现象**

`PhoenixAClient.get_strategy_market_bars()` 固定写了：

- `limit = 5000`
- `offset = 0`

没有循环翻页。

**影响**

- 对长区间分钟线或大样本回测，可能 silent truncate
- cache 还会把这个“不完整数据”写入本地，污染后续命中结果

**建议**

必须补 provider 级分页/迭代拉取，至少保证：

- daily/weekly 现状安全
- intraday 走循环拉取直到 exhausted

---

### P2-1. 前端 store/page 对 data options 加载失败时仍然允许继续操作，不符合设计里的“无 fallback”

**现象**

`workbench.store.ts`：

- `loadDataOptions()` 失败后只是 `_dataOptionsLoaded.set(true)`
- 没有错误态，也没有禁用交互
- 页面组件本身还有一套硬编码默认值：
  - `stock / zh_a / daily / nf`

**影响**

- 一旦 `/workbench/data-options` 异常，页面仍可操作
- 但用户实际使用的是前端硬编码默认值，而不是后端配置
- 这与“无 fallback”设计是冲突的

---

### P2-2. Workbench 的自动化测试覆盖明显偏后端底层，偏缺业务入口层

当前测试主要集中在：

- partition
- storage
- compaction
- cache_engine

但缺少：

- `config_manager` 行为测试（我已补基础）
- `workbench_routes` API 合约测试
- `market_data` service 测试
- `backtest` service 测试
- “source + dimensions + cache + phoenix fetch” 的端到端组合测试

---

### P2-3. 文档要求验证 `config-home.yaml / config-production.yaml`，但当前仓库里这两个文件不存在

**现象**

当前 `app/projects/artemis/config/` 下我只看到：

- `config.yaml`
- `task.yaml`

没有：

- `config-home.yaml`
- `config-production.yaml`

**影响**

- `available_sources()` 的设计和文档依赖这两个文件
- 但仓库当前状态下无法完成文档里的验证步骤

**结论**

这里至少存在文档/仓库状态不一致；如果这是因为敏感配置没提交，建议给一套 `*.example.yaml` 或最小样例文件。

---

## 4. 我认为当前最需要先做的三件事

### 第一优先级：统一“数据维度”的真实语义边界

明确：

- `asset_type/market/period/adjust` 是不是只用于 cache key？
- 还是它们必须完整影响上游 PhoenixA 查询？

如果是后者，就必须引入 provider abstraction，而不能继续只靠 `stock/hist/get_data`。

### 第二优先级：统一 `period/timeframe` 和 `adjust` 规范

至少要定义清楚：

- 标准入参字段名是什么
- `index` 的 adjust canonical 值是什么
- cache path 是否允许 optional adjust

### 第三优先级：补 Workbench 入口层测试

优先补：

1. `ConfigManager`
2. `market_data.get_market_bars`
3. `workbench_routes`
4. source + cache + partial miss + phoenix fetch 组合链路

---

## 5. 这次我已经顺手补的内容

### 代码修复

1. `artemis/core/config_manager.py`
   - override 由浅合并改成递归合并
   - reload 时清空 `_data_sources` 缓存

2. `artemis/engines/cache_engine/cache_engine.py`
   - 修复 partial partition hit 被误判为完整 cache hit 的问题

### 新增测试

1. `tests/test_config_manager.py`
   - 验证 nested config deep merge
   - 验证 reload 时 source cache 不会污染新配置

2. `tests/test_cache_engine_partial_miss.py`
   - 验证跨分区 partial hit 会触发回源补数，而不是返回不完整缓存

---

## 6. 最终结论

### 结论一句话

**这个系统现在已经具备“可用的 Workbench MVP + 可用的 cache phase1”，但离“通用数据维度工作台”还差一个关键抽象层：数据 provider / asset-type aware fetch contract。**

### 我的判断

- **代码质量整体不差**，尤其 cache 的底层实现推进得比较扎实
- **真正的问题不在“有没有写功能”**，而在于：
  - 设计文档已经把系统抽象成“多维 market-data workbench”
  - 但上游数据获取层仍然停留在“stock-hist 单一路径”

所以如果你接下来还会继续扩展 `index`、更多 market、更多 period，**建议尽快做一轮架构 refactor，而不是继续在现有接口上叠 patch。**

