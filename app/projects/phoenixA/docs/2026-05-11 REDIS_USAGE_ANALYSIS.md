# Redis 使用分析 — PhoenixA ROI 评估

## 背景

PhoenixA 已引入 Redis 组件（infra 层 universal client，支持 standalone/cluster/sentinel）。
本文档补充从 `internal/api/router_v2.go` 出发，对 PhoenixA 的 HTTP GET 读流量进行一次更完整的缓存 ROI 复盘。

## 当前缓存状态

| 组件 | 缓存方式 | TTL | 问题 |
|------|---------|-----|------|
| `CatalogService.getTables` | `sync.RWMutex + slice` | 5min | 重启丢失、无跨实例共享 |
| `CatalogService.GetDataDictionary` | `sync.RWMutex + struct` | 10min | 重启丢失、JSONB discovery 每次重建 |
| `SchemaDao.DiscoverFields` | 无 | — | 重复 schema 字段发现请求会重复打 DB |
| `SchemaDao.DiscoverJSONBKeysGeneric` | 无 | — | 每次全表扫描 + `jsonb_object_keys` |
| `WriteBuffer` | in-memory channel | — | 重启丢失、但单实例足够 |

## 基于 `router_v2.go` 的 GET 路由补充审查

之前的分析更偏 infra / metadata 视角，**没有完整覆盖 HTTP GET 读取面**。按 `router_v2.go` 复盘后，PhoenixA 的 GET 路由可以大致分成以下几类：

| 路由族 | 典型接口 | 数据特征 | Redis 结论 |
|------|------|------|------|
| Security | `/api/v2/securities/` `/count` | A 股基础证券主数据，更新低频、读取高频、结果稳定 | ✅ 适合做读时填充缓存 |
| Schema | `/api/v2/schema/fields` | JSONB / schema 发现型查询，重复请求收益高 | ✅ 适合做读时填充缓存 |
| Catalog | `/api/v2/catalog/*` | 已有进程内缓存，且大多基于 catalog/schema 元数据拼装 | ⚠️ 继续以内存缓存为主 |
| Taxonomy | `/api/v2/taxonomy/.../categories`、industry reads | 读多但也有持续写入/替换，需先保证 market 语义完整 | ✅ 已分阶段落地 |
| Bars | `/api/v2/bars/...` | 时间范围/字段/复权参数组合过多，动态性强 | ❌ 不建议做通用 Redis cache |
| Financial / Corporate Action | `/api/v2/financial/...` `/corporate-action/...` | 筛选维度多、分页多、key 爆炸 | ❌ 不建议做通用 Redis cache |
| KG / Graph / Strategy Run | `/api/v1/kg/*` `/api/v1/graph/*` | 查询强业务化，更新较频繁或结果时效性强 | ❌ 暂不建议 |
| OpenAPI / Buffer Stats | `/openapi.yaml` `/api/v2/buffer/stats` | 文件读 / 运行态数据 | ❌ 无明显 Redis 价值 |

> 结论：原先“Redis ROI 整体不高”的方向判断没有错，但**不够全面**。
> 真正遗漏的，是 HTTP GET 层里最值得优先做的两类：
> 1. 全量证券主数据读取
> 2. Schema / JSONB 字段发现

## ROI 分析

### 高 ROI — JSONB / Schema 字段发现缓存

**现状**:
- `DiscoverFields` 会重复做 domain/type 维度的字段发现
- `DiscoverJSONBKeysGeneric` 每次调用执行 `jsonb_object_keys()` 全表扫描（采样 200 行）
- `data-dictionary` 构建时会对所有 JSONB 列重复触发发现逻辑

对 `financial_statement` 这类表目前耗时还可接受，但对大型 JSONB 表和频繁重复请求来说，Redis 命中收益已经足够明确。

**Redis 方案**:
- `GET /api/v2/schema/fields` 做 read-through cache
- `DiscoverJSONBKeysGeneric` 做 read-through cache，使 `catalog/data-dictionary` 也能间接受益

**Key 设计**:
- `phoenixa:cache:v1:schema:fields:{domain}:{type}:{sample_size}`
- `phoenixa:cache:v1:schema:jsonb_keys:{schema}:{table}:{column}:{sample_size}`

**TTL**: 24h

**失效策略**:
- 只做 TTL 自然过期
- 不做写时更新
- 理由：这是“元数据发现结果”，允许短时间延迟，不值得把写链路复杂化

补充：为了覆盖极少数“新增写入任务 / 新数据源 / 新字段刚上线”的情况，现在支持显式刷新绕过 Redis：
- `/api/v2/schema/fields?...&refresh=true`
- `/api/v2/catalog/tables/{schema}/{table}?refresh=true`
- `/api/v2/catalog/data-dictionary?refresh=true`

**结论**: ✅ 值得做，且本轮已实现。

### 高 ROI — 全量证券主数据缓存

**现状**:
`/api/v2/securities/` 默认就是证券主数据查询；PhoenixA 的一个高频场景是“读取 A 股全量股票列表”以及对应的 `/count`。这类数据具备非常典型的缓存特征：
- 更新低频
- 读取高频
- 结果相对稳定
- miss 后从 DB 加载并回填 Redis 即可

**Redis 方案**:
- 仅缓存**无过滤、无分页**的全量查询
- 不缓存带 `name/exchange/status/symbol/symbols/limit/offset` 的动态查询
- miss 时查 DB，再写回 Redis

**Key 设计**:
- 列表：`phoenixa:cache:v1:security:list:{asset_type}:{market}`
- 数量：`phoenixa:cache:v1:security:count:{asset_type}:{market}`

**TTL**:
- 列表：24h
- 数量：24h

**失效策略**:
- `cache-aside` / read-through
- `BatchUpsert` / `DeleteAll` 后做**最佳努力删除**聚合 key
- 不做写时重建，避免写链路耦合缓存

这意味着正常通过 PhoenixA API 写入证券主数据时，Security cache 是可主动失效的；只有绕过 PhoenixA 直接改库时，才回退到 TTL 自然过期。

**结论**: ✅ 值得做，且本轮已实现。

### 中 ROI — Catalog 表元数据缓存

**现状**:
`getTables()` 使用 `sync.RWMutex` 缓存 5 分钟。重启后一次请求触发 `ListTables`（多个 `pg_class` / `information_schema` 查询）+ `ANALYZE`，耗时约 `100~500ms`。

**Redis 方案**:
缓存序列化后的 `[]TableCatalogEntry`，TTL = 5min。

| 指标 | 当前 | 引入 Redis 后 |
|------|------|-------------|
| 重启后首次请求延迟 | ~500ms（pg 查询） | ~5ms（Redis 读取） |
| 内存占用 | Go heap ~50KB | Redis ~50KB |
| 多实例共享 | 不支持 | 支持 |

**结论**: ⚠️ PhoenixA 目前仍是**单实例服务**，这里的 Redis ROI 依然不高，继续保持进程内缓存即可。

补充说明：`/api/v2/catalog/data-dictionary`、`/capabilities`、`/business-overview` 本轮虽然没有直接迁移到 Redis，但会间接受益于：
- 现有 `getTables()` / `GetDataDictionary()` 内存缓存
- 新增的 schema / JSONB 发现 Redis 缓存

### 中高 ROI — Taxonomy 读接口缓存

**已落地接口**:
- `/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories`
- `/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/{code}`
- `/api/v2/taxonomy/by_security/{symbol}`
- `/api/v2/taxonomy/{source}/{taxonomy}/mapping/by_category/{categoryCode}`
- `/industry-constituents/by_index/{indexCode}`
- `/industry-constituents/by_stock/{symbol}`

**判断**:
这些接口确实比 bars / financial 更适合缓存，但也伴随着：
- upsert / replace / sync 写入链路较多
- 参数维度多（source/taxonomy/market/page/page_size/date/indexCode）
- 失效面较大

本轮在补缓存前，先修正了 industry 读取链路中 `market` 未完整透传的问题，因此：
- 调用方仍沿用现有 v2 path 参数即可
- 不需要新增参数
- 新缓存 key 会把 `market` 纳入维度，保证结果一致性

缓存策略上，本轮也做了一个重要收敛：
- 对 `categories`、`mapping/by_category`、`constituents/by_index` 这类分页接口，不再把 `page/page_size` 编入 key
- 改为缓存稳定全集，再由服务层做切页

这样可以明显减少 key 碎片，提高跨页命中率。

同时，以下两个候选在重新评估后**明确不做 Redis cache**：
- `/industry-weights/{indexCode}?trade_date=...`
- `/industry-daily?index_code=...&start_date=...&end_date=...`

原因是这两类查询的组合维度接近无限，个人用户场景下也容易形成大量低复用 key，ROI 不如预期。

**TTL 调整**:
- category list/get：30d
- mapping by symbol/category：14d
- constituents：14d

**结论**: ✅ 已分阶段落地；taxonomy 中“低基数、稳定结果”的 GET 读取面已成为 PhoenixA 中 Redis ROI 较高的一组接口。

### 低 ROI — Write Buffer 持久化

**现状**: `WriteBuffer` 用 Go channel + goroutine 缓冲写入，8192 容量，3 秒或 2000 行 flush。

**Redis 方案**: 用 Redis Stream/List 替代 channel。

**结论**: ❌ 不建议。单实例无需分布式缓冲，增加序列化复杂度，crash recovery 的概率极低（数据来自 Artemis 定时任务，可重跑）。

### 低 ROI — Rate Limiting

**结论**: ❌ PhoenixA 是内部服务，API 不暴露公网。当前无 rate limiting 需求。如果未来开放给外部，可用 Redis + sliding window。

### 不适用 — Session Store

**结论**: ❌ PhoenixA 无认证/鉴权，不需要 session。

## 总结

| 场景 | ROI | 建议 |
|------|-----|------|
| JSONB / Schema 字段发现缓存 | 高 | ✅ 已实现 |
| 全量证券列表 / 数量缓存 | 高 | ✅ 已实现 |
| Catalog 元数据缓存 | 中 | 单实例无需，保持现状 |
| Taxonomy 读接口缓存 | 中高 | ✅ 已实现 |
| Write Buffer | 低 | 不做 |
| Rate Limiting | 低 | 内部服务不需要 |
| Session | N/A | 不适用 |

**修正后的最终建议**:
Redis 在 PhoenixA 当前阶段**不适合全面铺开**，但也**并非完全没有 ROI**。最值得立即落地的是：
- 全量证券主数据读取 cache
- schema / JSONB 元数据发现 cache

而以下场景继续保持不做或延后：
- 多实例之前，不把 Catalog 全量迁移到 Redis
- 不用 Redis 替代 WriteBuffer
- 内部服务阶段不做 rate limiting / session
- taxonomy 等读接口等观测到稳定热点后再进入下一阶段
