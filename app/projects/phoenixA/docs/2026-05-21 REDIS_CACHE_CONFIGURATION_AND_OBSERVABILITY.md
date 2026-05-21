# PhoenixA Redis Cache 配置与观测说明

## 目标

本文档说明 PhoenixA 当前已落地的 Redis cache 用法，包括：
- 如何开启
- key 总览
- TTL 设计
- 命中 / 失效预期
- 后续适合扩展的缓存点

当前 Redis cache 采用 **cache-aside / read-through** 模式：
- 读请求命中 Redis → 直接返回
- 未命中 → 查 DB，再回填 Redis
- 写请求不重建缓存，只做 **best-effort 失效**

## 如何开启

PhoenixA 已通过 infra 层集成 Redis universal client，支持：
- `single`
- `cluster`
- `sentinel`

在 `config/config.yaml` 中增加或启用：

```yaml
redis:
  enabled: true
  mode: single
  addresses:
    - 127.0.0.1:6379
  username: ""
  password: ""
  db: 0
  sentinel_master: ""
  pool_size: 16
  min_idle_conns: 4
  conn_max_lifetime: 30m
  conn_max_idle_time: 10m
  dial_timeout: 3s
  read_timeout: 1s
  write_timeout: 1s
```

如果 `redis.enabled: false`：
- PhoenixA 仍然正常工作
- 所有缓存逻辑自动退化为 DB 直查
- 不影响现有 API 行为

## 当前 key 总览

### 1. Security

| 场景 | key 模式 | 说明 |
|------|---------|------|
| 全量证券列表 | `phoenixa:cache:v1:security:list:{asset_type}:{market}` | 仅缓存无过滤、无分页聚合查询 |
| 全量证券数量 | `phoenixa:cache:v1:security:count:{asset_type}:{market}` | 仅缓存无过滤聚合 count |

### 2. Schema / JSONB Discovery

| 场景 | key 模式 | 说明 |
|------|---------|------|
| schema 字段发现 | `phoenixa:cache:v1:schema:fields:{domain}:{type}:{sample_size}` | 对 `/api/v2/schema/fields` 生效 |
| JSONB key 发现 | `phoenixa:cache:v1:schema:jsonb_keys:{schema}:{table}:{column}:{sample_size}` | 供 catalog / data-dictionary 复用 |

### 3. Taxonomy 第二批缓存

| 场景 | key 模式 | 说明 |
|------|---------|------|
| 分类列表 | `phoenixa:cache:v1:taxonomy:category:list:{source}:{taxonomy}:{market}:{filter_token}` | 缓存稳定全集，服务端再切页 |
| 分类详情 | `phoenixa:cache:v1:taxonomy:category:get:{source}:{taxonomy}:{market}:{code}` | 单分类详情 |
| 按证券查映射 | `phoenixa:cache:v1:taxonomy:mapping:by_symbol:{symbol}` | 对 `/api/v2/taxonomy/by_security/{symbol}` 生效 |
| 按分类查映射 | `phoenixa:cache:v1:taxonomy:mapping:by_category:{source}:{taxonomy}:{category_code}` | 缓存稳定全集，服务端再切页 |

### 4. Taxonomy 第三批缓存

| 场景 | key 模式 | 说明 |
|------|---------|------|
| 按指数查成分股 | `phoenixa:cache:v1:taxonomy:constituents:by_index:{source}:{taxonomy}:{market}:{index_code}` | 缓存稳定全集，服务端再切页 |
| 按股票查所属指数 | `phoenixa:cache:v1:taxonomy:constituents:by_symbol:{source}:{taxonomy}:{market}:{symbol}` | 对 `/industry-constituents/by_stock/{symbol}` 生效 |

> 说明：`industry-weights` 与 `industry-daily` 的组合维度过高，本轮评估后不再使用 Redis cache。

## TTL 设计

| 场景 | TTL | 原因 |
|------|-----|------|
| Security 全量列表 | 24h | 主数据更新低频，且 PhoenixA 写路径会主动失效 |
| Security 数量 | 24h | 同样具备写路径失效，适合拉长 TTL |
| Schema 字段发现 | 24h | 元数据变化极少，特殊情况下可手动 refresh |
| JSONB key 发现 | 24h | 同上 |
| Taxonomy 分类列表 | 30d | 分类体系变化极低频，且已有写路径失效 |
| Taxonomy 分类详情 | 30d | 单节点详情同样极低频变化 |
| Taxonomy 按证券查映射 | 14d | 结构稳定，写链路可触发失效 |
| Taxonomy 按分类查映射 | 14d | 同上 |
| Taxonomy 按指数查成分股 | 14d | 结构性数据，通常按日或更低频更新 |
| Taxonomy 按股票查所属指数 | 14d | 同上 |

## 命中 / 失效预期

## Security

### 命中预期
高频命中场景：
- 读取 A 股全量证券列表
- 读取证券总数
- 前端下拉、批量任务、BI/SDK 初始化阶段反复拉取相同聚合结果

### 失效策略
- `BatchUpsert` 后按涉及的 `(asset_type, market)` 删除聚合 key
- `DeleteAll` 后按指定范围删除 key；如果范围不完整，则做 pattern 失效

这意味着：
- 正常通过 PhoenixA API 写入证券主数据时，Security cache 会立即失效
- 如果是绕过 PhoenixA 直接改库，则回退到 TTL 自然过期

## Schema / JSONB Discovery

### 命中预期
高频命中场景：
- `/api/v2/schema/fields`
- `/api/v2/catalog/data-dictionary`
- 表详情页 / LLM 元数据发现反复触发相同采样查询

### 失效策略
- 不做写时更新
- 只依赖 TTL 自然过期

原因：这是“元数据观察值”，允许短暂过期，不值得为此耦合写链路。

但为了覆盖极少数“新增写入任务 / 新数据源写入 / 新字段突然出现”的场景，本轮增加了显式绕过缓存的方式：
- `GET /api/v2/schema/fields?...&refresh=true`
- `GET /api/v2/catalog/tables/{schema}/{table}?refresh=true`
- `GET /api/v2/catalog/data-dictionary?refresh=true`

这些请求会跳过 Redis 中的 schema / JSONB discovery cache，并用最新 DB 结果回填缓存。

## Taxonomy

在第三批缓存落地前，taxonomy 某些 industry 读取接口存在一个语义风险：虽然 URL path 上有 `{market}`，但底层查询并没有完整使用该条件。

本轮已先修正这一点：
- `industry-constituents/by_index`
- `industry-constituents/by_stock`
- `industry-weights/{indexCode}`
- `industry-daily`

现在这些读取链路会把 `market` 从 controller → service → dao 全链路透传，因此新增缓存不会改变调用方语义，只会让结果更快。

另外，分页型 taxonomy cache 本轮也做了调整：
- 不再把 `page` / `page_size` 直接编码进 key
- 改为缓存稳定的“全集结果”
- 再由服务层做切页

这样可以避免 page/page_size 变化带来的 key 爆炸和命中率下降。

### 命中预期
高频命中场景：
- 行业分类浏览（categories list/get）
- 因子/选股链路按证券查行业（`by_security/{symbol}`）
- 下游调试或前端按分类查看成分股映射（`mapping/by_category`）
- 下游按指数查看成分股、按股票查看所属指数时的重复拉取

### 失效策略

#### Categories
以下写操作会使分类缓存失效：
- `BatchUpsertCategories`
- `DeleteCategory`

失效方式：
- 删除 `category:list` 范围缓存
- 删除 `category:get` 范围缓存
- 同时删除全部 `mapping:by_symbol` 缓存（因为分类名称/派生标记变动会影响 enriched 响应）

#### Mappings
以下写操作会使映射缓存失效：
- `BatchUpsertMappings`
- `ReplaceStocksForCategories`
- `ReplaceCategoriesForSymbols`
- `DeleteMapping`
- `SyncMappingsFromConstituents`

失效方式：
- 精确删除相关 symbol key
- pattern 删除相关 category key
- 对大范围同步（`SyncMappingsFromConstituents`）做 source/taxonomy 级别 pattern 失效

#### Industry reads
以下写操作会使 industry 成分股缓存失效：
- `BatchUpsertConstituents`

失效方式：
- 对相关 `index_code` 做 pattern 失效
- 对成分股写入同时精确清理 `by_symbol` key

`industry-weights` 与 `industry-daily` 当前不走 Redis cache，因此不额外引入失效复杂度。

## 观测建议

### 1. 观察 key 数量

```powershell
redis-cli KEYS "phoenixa:cache:v1:*"
```

更推荐生产环境使用 `SCAN`：

```powershell
redis-cli SCAN 0 MATCH "phoenixa:cache:v1:*" COUNT 200
```

### 2. 查看具体 TTL

```powershell
redis-cli TTL "phoenixa:cache:v1:security:list:stock:zh_a"
redis-cli TTL "phoenixa:cache:v1:taxonomy:mapping:by_symbol:600519"
```

### 3. 观察缓存内容大小

```powershell
redis-cli MEMORY USAGE "phoenixa:cache:v1:security:list:stock:zh_a"
```

### 4. 建议日志观测点

当前代码已对 Redis get/set/del 失败输出 warning 日志。建议重点观察：
- `security ... redis cache get/set failed`
- `taxonomy ... redis cache get/set failed`
- `schema ... redis cache get/set failed`
- `... cache invalidation failed`

如果后续需要更精细观测，建议新增：
- cache hit / miss counter
- invalidation counter
- Redis round-trip latency histogram

## 为什么 taxonomy 只做第二批中的一部分

上一轮之所以没有直接缓存这些接口，是因为当时 `market` 维度没有完整穿透到 DAO 读查询。本轮已先修复语义，再重新筛选缓存点，因此调用方对接口参数**无感知**：
- v2 路由本来就已经在 path 中携带 `{market}`
- 本轮只是让读取链路真正使用这个条件，并据此生成缓存 key

同时，本轮主动撤销了两个高基数缓存候选：
- `industry-weights/{indexCode}?trade_date=...`
- `industry-daily?...`

原因是：
- query 组合接近无限
- page/page_size 之外还会叠加 date range 组合
- 对个人用户场景来说，Redis 中会更容易积累大量低复用 key
- 收益不一定覆盖复杂度和内存占用

## 后续适合扩展的缓存点

优先级建议：

### 下一阶段候选
1. `industry-weights/{indexCode}?trade_date=...`
   - 如果后续调用稳定集中在“最新交易日”或少数固定日期，可再考虑只缓存热点日期

2. `industry-daily?index_code=...&start_date=...&end_date=...`
   - 如果后续调用模式稳定在标准窗口（最近 30/90/250 天），可只缓存这些标准窗口

3. `catalog/overview` / `catalog/business-overview` / `catalog/capabilities`
   - 如果未来变成多实例部署，可考虑从进程内缓存迁移至 Redis

4. Graph / KG 只读查询
   - 仅在出现稳定热点查询模板时评估
   - 不建议现在做通用缓存

## 结论

PhoenixA 当前的 Redis 使用策略应当是：
- 不全面铺开
- 只缓存高复用、低失效成本、结果稳定的 GET 读取面

当前已落地的高价值缓存层：
- Security 聚合读取
- Schema / JSONB 元数据发现
- Taxonomy 分类与核心映射读取
- Taxonomy 成分股稳定读取（按 index / 按 symbol）

其中当前“可主动控制失效/刷新”的能力可以总结为：
- Security：有写路径失效
- Schema / JSONB：默认靠 TTL，但支持 `refresh=true` 显式绕过并回填
- Taxonomy：有写路径失效





