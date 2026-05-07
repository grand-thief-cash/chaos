# Refactor Plan — Workbench 数据维度、Provider Layer 与 Cache Coverage

> 日期: 2026-04-13
> 目标: 按 review 结论重构 Workbench 查询 contract、Provider 抽象、缓存覆盖策略与 PhoenixA 拉取方式

---

## 1. 为什么需要这次 refactor

当前的问题不是简单的“少几个参数”，而是**抽象层位置不对**：

- UI / config / cache 已经在表达一个通用数据域：
  - `asset_type`
  - `market`
  - `period`
  - `adjust`
- 但上游 fetch 仍然是：
  - `PhoenixAClient.get_strategy_market_bars()`
  - 固定打到 `/api/v1/stock/hist/get_data`

这会让系统出现一种假象：

> 看起来支持多维，实际上只有 stock-hist 这条链路是真的。

同时，结合这次 review 后已经确认了几条设计决策，需要在 refactor 里明确固化：

1. **`source` 与 `data_options` 相互独立**  
   `source` 只是选择后端 PhoenixA/配置环境；`data_options` 是全局静态的 Workbench UI 选项定义，当前所有 source 共用同一套配置。

   当前 source 命名也需要收敛为清晰语义：
   - `relx`：当前本机/当前配置环境
   - `home`
   - `production`

   不再保留 `default` 这种语义含糊的名字。

2. **`index` 不展示 adjust，但后端必须归一化为固定值 `nf`**  
   这样 cache path、provider key、日志维度都保持稳定，不引入 optional path segment。

3. **cache 不仅要避免 partial-hit 误判，还要能表达“覆盖范围”**  
   用户关心的不是只修一个 bug，而是：
   - 历史缓存中间断档怎么办
   - 长时间没有查询但数据持续更新怎么办
   - 每天更新、任意时间查询时会不会漏数据

4. **PhoenixA 拉取不能继续依赖单次 `limit=5000`**  
   长区间分钟线和未来更多资产类型，都要求 provider 侧具备分页/分段拉取能力。

5. **系统内部只保留 `period`，不再把 `timeframe` 作为内部 alias**  
   `timeframe`、`frequency` 这类名字只允许出现在外部 SDK / 外部 HTTP API 的适配层；Chaos / Artemis 内部模型、服务、缓存、provider 一律统一为 `period`。

因此建议把 refactor 的重点放在：

1. **统一 contract**
2. **引入 provider abstraction**
3. **把 cache key、coverage 语义与 provider key 对齐**

---

## 2. 重构目标

### 目标 1：把 Workbench 的“查询语义”定义成统一对象

建议引入一个统一查询模型，例如：

```python
class MarketDataQuery(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    asset_type: str
    market: str
    period: str
    adjust: str = "nf"
    source: str | None = None
    use_cache: bool = True
```

建议同时补一个归一化结果对象，例如：

```python
class NormalizedDimensions(BaseModel):
    asset_type: str
    market: str
    period: str
    adjust: str
```

```python
def normalize_dimensions(*, asset_type: str, market: str, period: str, adjust: str | None) -> NormalizedDimensions:
    ...
```

其中核心规则明确为：

- `period` 是内部唯一标准名
- `timeframe` / `frequency` 不允许进入内部 service / cache / provider contract
- `asset_type == "index"` 时，无论前端是否传空值，都统一归一化为 `adjust="nf"`

边界映射原则：

- **外部 HTTP / SDK 入参** 可以保留各自原生字段名
- **进入 Artemis 内部领域模型之前** 必须统一映射为 `period`
- **调用外部 SDK / PhoenixA 之前** 再从 `period` 映射回外部系统要求的字段名（例如 `timeframe`、`frequency`）

这样做的好处：

- API 层不再散落一堆 query/body 参数
- service/cache/provider 共用一个语义模型
- 更容易加验证和归一化

---

### 目标 2：把 `period` 设为内部唯一标准名

统一规则：

- 外部 API 接受 `period`
- service / cache / provider / 前端 store 内部全部只保留 `period`

补充约束：

- Chaos / Artemis 自定义接口、内部 model、日志、测试计划里统一只出现 `period`
- 如果某个外部 SDK 或外部 HTTP API 要求 `timeframe` / `frequency`，则在 boundary adapter 中单点映射
- 不再把 `timeframe` 当作系统内部 alias，以免继续混淆
- response 建议统一为 `period`

避免继续混用。

---

### 目标 3：引入 Provider 层，而不是让 `market_data.py` 直接依赖 PhoenixA stock endpoint

建议新增：

```python
artemis/services/workbench/providers/
    base.py
    phoenix_stock_provider.py
    phoenix_index_provider.py
    registry.py
```

抽象接口：

```python
class MarketDataProvider(Protocol):
    def fetch_bars(self, query: MarketDataQuery) -> list[dict]:
        ...
```

建议在 provider 层显式接收的是**已经归一化过的 query**，而不是原始参数，这样可以确保：

- cache key 与 provider key 语义一致
- `index -> nf` 只做一次，不在各层重复判断
- `period/timeframe` 混名问题不会向下游扩散

Registry 依据 `(asset_type, market)` 或更完整的 key 做分发：

```python
provider = provider_registry.resolve(
    asset_type=query.asset_type,
    market=query.market,
)
rows = provider.fetch_bars(query)
```

这样才能把：

- stock
- index
- future / etf（未来）

自然扩展出来。

这部分就是本次用来解决 `P0-1` 的主方案：  
**把“多维数据语义”真正落到 Provider 选择与上游 endpoint 选择上，而不只是停留在 UI 和 cache 路径层。**

---

### 目标 4：明确 `adjust` 的 canonical 策略

推荐规则：

- API/UI 上：`index` 可以隐藏 adjust selector
- service/provider/cache 内部：统一归一化到一个 canonical 值
- 推荐 `index -> nf`
- `stock` 则继续沿用 `nf/qfq/hfq`

这样 cache path 永远稳定为：

```text
asset_type/market/period/adjust/symbol/partition.arrow
```

不引入 optional path segment。

这也是本次已经确认采纳的方案，不再保留“adjust 可为空 path segment”的备选实现。

---

### 目标 5：明确 `source` 与 `data_options` 的边界

当前按业务确认，二者的关系应该定义为：

- `source`：选择后端数据源环境（`relx` / `home` / `production`）
- `data_options`：Workbench 的全局静态维度选项定义
- 所有 source 共用一套 `data_options`
- production source 只是数据更全，不代表要返回另一套 options

因此当前阶段**明确不做** `source-aware data options`，而是在文档与实现中明确：

> data_options 当前为顶层全局静态配置，与 source 无关。

这里也意味着：

- Source 选择器只是选择后端数据环境
- 不是切换一套新的维度配置
- 各环境差异主要体现在“数据覆盖范围与数据量”，而不是“维度定义不同”

---

## 3. 推荐的分阶段落地方式

## Phase 1 — Contract Stabilization（低风险，优先做）

### 3.1 改动点

- 新增 `MarketDataQuery` / `NormalizedDimensions`
- 路由层支持：
  - `period` 标准参数
- 后端内部统一只用 `period`
- 增加 `normalize_dimensions()`：
  - `asset_type`
  - `market`
  - `period`
  - `adjust`
- `index` 自动归一化为 `adjust="nf"`
- response 中补 `period`
- 明确 `source` 与 `data_options` 独立，`GET /workbench/data-options` 不接 source 参数
- source 命名统一为 `relx/home/production`
- 页面侧不再保留与后端配置冲突的硬编码默认值

### 3.2 涉及文件

- `artemis/models/workbench.py`
- `artemis/api/http_gateway/workbench_routes.py`
- `artemis/services/workbench/market_data.py`
- `artemis/services/workbench/backtest.py`
- `cthulhu/.../workbench.model.ts`
- `cthulhu/.../workbench-api.service.ts`
- `cthulhu/.../market-data.page.ts`
- `cthulhu/.../strategy-config.component.ts`

### 3.3 验收标准

- `period` 成为标准字段
- 内部 contract 中不再出现 `timeframe`
- `index` 请求不会产生空 adjust 目录
- `data_options` 被明确为全局静态配置，和 source 解耦
- source 命名不再使用 `default`

---

## Phase 2 — Provider Abstraction（核心架构升级）

### 3.4 新目录建议

```text
artemis/services/workbench/providers/
  base.py
  registry.py
  phoenix_stock_hist_provider.py
  phoenix_index_hist_provider.py
  models.py
```

### 3.5 设计建议

#### `base.py`

```python
class MarketDataProvider(ABC):
    @abstractmethod
    def supports(self, *, asset_type: str, market: str) -> bool: ...

    @abstractmethod
    def fetch_bars(self, query: MarketDataQuery) -> list[dict]: ...
```

#### `registry.py`

```python
class ProviderRegistry:
    def register(self, provider: MarketDataProvider) -> None: ...
    def resolve(self, *, asset_type: str, market: str) -> MarketDataProvider: ...
```

#### `market_data.py`

```python
provider = provider_registry.resolve(
    asset_type=query.asset_type,
    market=query.market,
)
rows = provider.fetch_bars(query)
```

说明：这里的 `query.period` 已经是内部统一字段；如果某个 provider 最终需要调用外部 PhoenixA endpoint 且该 endpoint 参数名叫 `timeframe`，则由 provider 内部适配，不允许把 `timeframe` 继续向上游传播回 service/model。

建议补一个 provider 层内部契约：

```python
class FetchResult(BaseModel):
    bars: list[dict]
    complete: bool
    fetched_start: str
    fetched_end: str
```

`complete=True` 的语义是：provider 确认在自己的分页/分段规则下，已经把目标查询范围完整拉完。  
只有 `complete=True` 的结果才允许被提升为“完整覆盖的 cache 写入结果”。

### 3.6 好处

- Artemis 不再把 PhoenixA stock API 写死在 workbench service 里
- 后面要支持 index / ETF / future 时，不会污染 cache 层
- provider 层可以独立做分页、字段映射、兼容转换
- provider 层可以独立表达“本次回源是否完整”，避免把不完整分页结果写脏缓存

---

## Phase 3 — PhoenixA Client 拆分与分页补全

### 3.7 问题

当前 `PhoenixAClient.get_strategy_market_bars()`：

- stock-only path
- fixed `limit=5000`
- 无分页
- 无法表达“本次拉取是否完整覆盖了查询范围”

### 3.8 建议

拆成更明确的 client 方法：

```python
def get_stock_hist_bars(...): ...
def get_index_hist_bars(...): ...
def iter_stock_hist_bars(...): ...
def iter_index_hist_bars(...): ...
```

provider 只依赖它需要的那一个方法，不再用一个名字模糊的 `get_strategy_market_bars()` 包打天下。

同时要补充一个重要的 boundary 原则：

- `PhoenixAClient` / SDK adapter 可以使用外部系统原生命名（例如 `timeframe`）
- 但 adapter 的上层（service / provider registry / cache）仍然只使用 `period`
- 也就是说，`timeframe` 是 PhoenixA 适配细节，不是 Artemis 领域模型字段

进一步建议：

1. **分页责任放在 provider/client，而不是 cache 层**
2. **provider 负责把多页结果拼成完整 OHLCV 列表**
3. **provider 必须显式判断 exhausted 条件**，例如：
   - 返回条数 < page_size
   - offset/游标达到末尾
   - 时间范围达到请求 end_date
4. **长区间分钟线支持分段拉取**，例如按月/按周切分后再分页

推荐的调用形态：

```python
rows = list(provider.iter_bars(query))
```

或：

```python
result = provider.fetch_bars(query)
assert result.complete is True
```

### 3.9 验收标准

- 长时间区间分钟线不会被 silent truncate
- 不同 asset_type 走不同 endpoint
- provider 返回统一 OHLCV schema
- provider 能证明“查询范围已完整拉取完成”

---

## Phase 4 — Cache Coverage & Backfill（建议纳入本次 refactor 范围）

这一阶段主要回答用户在 review 中提出的真实 concern：

> 如果缓存以前只更新到 `2026-04-01`，后面一段时间没更新也没查询；后来数据已经更新到 `2026-06-01`，这时查询 `2026-05-01 ~ 2026-06-01`，缓存中间空了一段，会不会有问题？

### 3.10 结论

**正确性上不能有问题，但当前实现仍有优化空间。**

在修复 partial-hit 误判后：

- 不会再把“不完整缓存”当成完整结果直接返回
- 但如果缺口存在，系统仍可能采用“整段回源”的粗粒度策略
- 这会带来性能浪费，甚至在 provider 无分页时造成不完整拉取风险

因此建议正式引入 coverage-aware cache 语义。

这里要特别说明：**coverage-aware cache 语义** 和之前设计里提到的 **SQLite cache index** 不是同一件事，但两者可以强相关。

- **coverage-aware cache**：是“如何判断缓存是否完整、何时回源、如何 backfill”的语义与策略层
- **SQLite cache index**：是“把缓存元数据存到哪里、如何查询元数据”的存储实现层

可以理解为：

- coverage-aware = correctness model / decision model
- SQLite cache index = metadata repository / persistence layer

二者关系是：

> coverage-aware cache 可以建立在 SQLite cache index 之上，但它们不是一回事。

### 3.11 设计目标

把 cache 查询结果分成三种状态：

1. **Full Hit**：请求覆盖范围内所有目标分区都有完整 base 数据
2. **Partial Hit**：部分分区有数据，但不能证明整个查询范围都完整覆盖
3. **Miss**：完全无覆盖

行为定义：

- `Full Hit` → 直接读缓存返回
- `Partial Hit` → 只把缓存当作“已知覆盖片段”，必须执行 backfill
- `Miss` → 全量回源

### 3.12 Backfill 策略

推荐从“按缺失分区回源”开始，不必一上来做日级缺口索引：

1. 先根据 `period` + partition rule 计算请求涉及的 partitions
2. 找出缺失的 base partitions
3. 只对缺失 partitions 对应的时间范围执行回源
4. 回源完成后写入对应分区 cache
5. 最后统一从 cache + 新回源结果组装完整输出

示例：

```text
缓存已有:
  2026_04.arrow
缺失:
  2026_05.arrow
  2026_06.arrow

查询:
  2026-05-01 ~ 2026-06-01

处理:
  只回源 2026-05-01 ~ 2026-06-01 对应缺失分区
```

### 3.13 关于“缓存中间断档”的进一步说明

如果未来出现更细粒度的问题，例如：

- `2026_05.arrow` 文件存在
- 但文件内部只到 `2026-05-10`
- `2026-05-11 ~ 2026-05-31` 实际缺失

那么只靠“base 文件是否存在”是不够的。

因此建议后续加一层**partition coverage metadata**，至少记录：

```python
class PartitionCoverage(BaseModel):
    base_name: str
    min_date: str | None
    max_date: str | None
    complete: bool
```

这类 coverage metadata 很适合落到之前设计过的 SQLite cache index 中，例如给每个 partition 记录：

- `asset_type`
- `market`
- `period`
- `adjust`
- `symbol`
- `base_name`
- `min_date`
- `max_date`
- `complete`
- `last_fetch_at`
- `row_count`

有了它以后，系统就能回答：

- 这个分区是否只是“存在文件”
- 还是“已经完整覆盖到最新边界”

### 3.14 每天数据都更新、任意查询会不会出问题？

如果没有 coverage 语义，长期来看会有两个风险：

1. **漏补问题**：文件存在但内部范围不完整
2. **重复拉取问题**：每次都按整段粗粒度补数据

引入 coverage-aware backfill 后，正确策略应是：

- 日常增量更新：继续写 `.inc.*.arrow`
- 用户查询：
  - 先判断目标分区 coverage
  - 缺失的范围回源补齐
  - 可选触发 compaction 或延后 compaction

所以结论是：

> 只要 backfill 逻辑基于 coverage，而不是仅基于“有没有文件”，缓存可以支持“每天持续更新 + 任意时间查询”，不会在正确性上出问题。

---

## 4. Cache 层建议同步做的小优化

### 4.1 固定引入 `CacheKey`

建议加一个轻量值对象：

```python
@dataclass(frozen=True)
class CacheKey:
    asset_type: str
    market: str
    period: str
    adjust: str
    symbol: str
```

作用：

- 降低 `cache.get(...)` / `put(...)` 参数串长
- 避免同一批维度在各层反复散传
- 更容易做日志和测试

### 4.2 Partial miss 后续继续升级成“缺分区定向回源”

这次我只修了“别把 partial hit 当 full hit”。

下一步可以升级为：

- 找出缺失 partitions
- 只回源缺失分区对应时间段
- 避免整段重拉

建议把这部分正式升级为：

- `CoverageResolver`
- `BackfillPlanner`
- `FetchResult.complete`
- `CacheIndexRepository`（SQLite 可作为默认实现）

三件套配合：

1. `CoverageResolver`：判断哪些分区完整、哪些缺失
2. `BackfillPlanner`：把缺失范围规划成一个或多个回源任务
3. `FetchResult.complete`：保证 provider 返回结果是完整的，才能安全写 cache
4. `CacheIndexRepository`：持久化 partition/file coverage metadata，支撑 resolver 与 planner

这部分不再建议只是“phase 1.5 优化项”，而是建议纳入本次 refactor 主体。

推荐的分层关系：

```text
CacheIndexRepository (SQLite 等)
        │
        ▼
CoverageResolver
        │
        ▼
BackfillPlanner
        │
        ▼
CacheEngine / Provider
```

---

## 5. 前端建议

### 5.1 Store 不要在页面组件里再保留一套硬编码默认值

当前：

- store 负责加载 options
- page/component 里又有 `stock / zh_a / daily / nf` 的本地默认值

建议改成：

- store 持有当前维度 state
- loadDataOptions 成功后由 store 选定默认项
- 页面只展示/修改 store state

这样可以避免：

- 后端 config 改了，前端默认值却没改
- data-options 请求失败时还在用 UI fallback 偷偷跑
- 明明已经确认 `data_options` 为全局静态配置，但前端仍混入另一套本地默认语义

### 5.2 失败态要显式化

建议：

- `dataOptionsLoaded`
- `dataOptionsLoading`
- `dataOptionsError`

没有 options 时不要允许发请求。

---

## 6. 测试策略建议

重构后建议新增以下测试层次：

### 6.1 Provider 单元测试

- stock provider 调对 endpoint
- index provider 调对 endpoint
- 分页逻辑完整
- schema 归一化正确
- `index` 请求被归一化为 `adjust=nf`

### 6.2 Service 单元测试

- `normalize_dimensions()`
- `get_market_bars()` cache hit/miss/provider error
- `run_backtest()` 对 query 透传正确
- `source` 与 `data_options` 独立的契约不被破坏
- gap/backfill 场景不会返回不完整结果
- 内部 service / provider contract 不再出现 `timeframe`

### 6.3 Route 合约测试

- Chaos 自定义 API 统一使用 `period`
- `index` 时 adjust 自动归一化
- `source` 非法返回 400
- `/workbench/data-options` 不依赖 source
- source 枚举值为 `relx/home/production`

### 6.4 端到端测试

- `source + dimensions + cache + provider` 全链路
- partial hit 自动补齐
- 空数据返回空状态
- 长时间未查询后跨月/跨年查询仍能正确补齐缺失区间
- 每日更新 + 任意范围查询不会因为中间断档返回错误结果

---

## 7. 我的建议结论

如果你问我“这次值不值得做 refactor”，我的判断是：

**值得，而且应该尽快做，但要控制范围。**

最合适的路径是：

1. **先做 Phase 1：contract stabilization**
2. **再做 Phase 2：provider abstraction**
3. **同步把 Phase 4 的 cache coverage/backfill 纳入主线**
4. 再做 PhoenixA client 分页和增量增强

这样可以同时解决：

- `P0-1`：stock-only fetch 的架构断层
- `P0-2`：index adjust 归一化
- `P0-3`：缓存中间缺口与持续更新查询问题
- `P1-3`：period/timeframe contract 漂移
- `P1-5`：PhoenixA 长区间 silent truncate 风险

避免你们后面继续在 `stock-only fetch` 和“只看文件存在性”的 cache 逻辑上叠 patch，最后越补越乱。

