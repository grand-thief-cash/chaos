# Redis 使用分析 — PhoenixA ROI 评估

## 背景

PhoenixA 已引入 Redis 组件（infra 层 universal client，支持 standalone/cluster/sentinel）。
本文档分析 PhoenixA 中 Redis 的实际使用场景和 ROI。

## 当前缓存状态

| 组件 | 缓存方式 | TTL | 问题 |
|------|---------|-----|------|
| CatalogService.getTables | sync.RWMutex + slice | 5min | 重启丢失、无失效机制 |
| CatalogService.GetDataDictionary | sync.RWMutex + struct | 10min | 重启丢失、JSONB discovery 每次重建 |
| SchemaDao.DiscoverJSONBKeysGeneric | 无缓存 | — | 每次全表扫描 + jsonb_object_keys |
| WriteBuffer | in-memory channel | — | 重启丢失、单实例足够 |

## ROI 分析

### 高 ROI — JSONB 字段发现缓存

**现状**: `DiscoverJSONBKeysGeneric` 每次调用执行 `jsonb_object_keys()` 全表扫描（采样 200 行），对 financial_statement（32行×47字段）耗时 ~10ms，但对大型 JSONB 表可能耗时数百 ms。data-dictionary 构建时对所有 JSONB 列都调用一次。

**Redis 方案**: 缓存发现结果，key = `jsonb:{schema}.{table}.{col}`，TTL = 30min

| 指标 | 当前 | 引入 Redis 后 |
|------|------|-------------|
| data-dictionary 构建耗时 | ~2s（15表×JSONB列） | ~50ms（缓存命中） |
| DB 负载 | 每次构建 15+ 次 JSONB 查询 | 首次后 0 查询 |
| 实现成本 | — | 低（1天，key-value 序列化） |

**结论**: ✅ 值得做。但优先级不高 — 当前 JSONB discovery 耗时可接受，且 TTL 内数据不会变化。

### 中 ROI — Catalog 表元数据缓存

**现状**: `getTables()` 用 `sync.RWMutex` 缓存 5 分钟。重启后第一次请求触发 `ListTables`（15 个 pg_class JOIN 查询）+ `ANALYZE`，耗时 ~100-500ms。

**Redis 方案**: 缓存序列化后的 `[]TableCatalogEntry`，TTL = 5min

| 指标 | 当前 | 引入 Redis 后 |
|------|------|-------------|
| 重启后首次请求延迟 | ~500ms（pg查询） | ~5ms（Redis 读取） |
| 内存占用 | Go heap ~50KB | Redis ~50KB |
| 多实例共享 | 不支持 | 支持 |

**结论**: ⚠️ PhoenixA 是**单实例服务**，不存在多实例共享需求。Go 进程内 `sync.RWMutex` 已经足够快。重启后 500ms 延迟可接受。**ROI 不高，不建议现在做。**

### 低 ROI — Write Buffer 持久化

**现状**: `WriteBuffer` 用 Go channel + goroutine 缓冲写入，8192 容量，3秒或2000行 flush。

**Redis 方案**: 用 Redis Stream/List 替代 channel

**结论**: ❌ 不建议。单实例无需分布式缓冲，增加序列化复杂度，crash recovery 的概率极低（数据来自 Artemis 定时任务，可重跑）。

### 低 ROI — Rate Limiting

**结论**: ❌ PhoenixA 是内部服务，API 不暴露公网。当前无 rate limiting 需求。如果未来开放给外部，可用 Redis + sliding window。

### 不适用 — Session Store

**结论**: ❌ PhoenixA 无认证/鉴权，不需要 session。

## 总结

| 场景 | ROI | 建议 |
|------|-----|------|
| JSONB Discovery 缓存 | 高 | Phase 2 可做，但不紧急 |
| Catalog 元数据缓存 | 中 | 单实例无需，保持现状 |
| Write Buffer | 低 | 不做 |
| Rate Limiting | 低 | 内部服务不需要 |
| Session | N/A | 不适用 |

**最终建议**: Redis 在 PhoenixA 当前阶段的 ROI **不高**。保留组件注册但暂不使用。如果未来：
- 引入多实例部署 → Catalog 缓存移到 Redis
- JSONB 表增长到百万行 → JSONB discovery 缓存
- API 暴露公网 → Rate limiting

届时再启用。
