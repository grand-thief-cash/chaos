# PhoenixA 批量写入缓冲层设计

> 日期：2026-05-07
>
> 背景：Artemis 下载任务在日常增量更新场景下，每个 symbol 仅拉取 1 条日线数据，
> 全市场 ~5000 只股票产生 ~5000 次独立的 HTTP 请求 → PhoenixA upsert → DB commit，
> 造成大量小事务开销。需要在 PhoenixA 侧引入写缓冲，将高频小写入合并为低频批写入。

---

## 一、问题分析

### 1.1 当前数据流

```
Artemis (OrchestratorUnit: STOCK_ZH_A_HIST_PARENT)
  │
  ├── plan(): 生成 ~5000 个 child spec
  │
  └── for each child (顺序执行):
        StockZhAHistChild
          ├── execute():    baostock.query_history_k_data_plus(symbol, start, end)
          ├── post_process(): DataFrame → {bars: [...], ext: [...]}
          └── sink():        HTTP POST → PhoenixA /api/v2/bars/.../upsert
                                          │
                                          └── BarsDao.BatchUpsert(bars)
                                              └── GORM CreateInBatches(bars, 1000)
                                              └── 1 transaction commit
```

### 1.2 两个典型场景对比

| 场景 | 每 symbol 数据量 | HTTP 请求数 | DB 事务数 | 总行数 |
|------|----------------|------------|----------|--------|
| **首次全量拉取** | ~1000-5000 行 | ~5000 | ~5000 | ~5M-25M |
| **每日增量更新** | **1 行** | **~5000** | **~5000** | **~5000** |

### 1.3 每日更新的性能瓶颈

每日增量时，5000 个 symbol 各产生：
1. **1 次 HTTP POST**（Artemis → PhoenixA）：序列化/反序列化、TCP 往返
2. **1 次 GORM CreateInBatches**（batch_size=1000，但实际只有 1 行）
3. **1 次 DB 事务 commit**

**核心问题**：5000 次网络往返 + 5000 次 DB commit 写入 5000 行数据。
如果合并为 1 次请求 + 1 次 commit，5000 行数据在 10ms 内即可写完。

---

## 二、方案对比：Kafka+Flink vs PhoenixA 内置缓冲

### 2.1 Kafka + Flink 方案

```
Artemis → Kafka Topic (bars_upsert) → Flink Window Aggregation → PhoenixA DB
```

| 维度 | 评估 |
|------|------|
| **额外资源** | Kafka 4-6GB + Flink 6-8GB = 10-14GB RAM（用掉全部预留） |
| **运维复杂度** | 新增 2 个有状态服务：Kafka broker + Flink JobManager/TaskManager |
| **引入价值** | 实时流处理、事件驱动、exactly-once 语义 |
| **当前需求匹配** | ❌ 过度设计 — 当前是**批处理调度**场景，不是实时流 |
| **部署改动** | Docker Compose 新增 2 个容器，网络配置、监控、日志 |
| **数据一致性** | 需要额外保障（Flink checkpoint + Kafka offset 管理） |
| **故障影响** | Kafka 挂 → 整个写入链路断，blast radius 大 |

### 2.2 PhoenixA 内置 Write Buffer 方案

```
Artemis → HTTP POST → PhoenixA Controller → WriteBuffer(channel) → 定时/定量 flush → DB
```

| 维度 | 评估 |
|------|------|
| **额外资源** | 0 — 纯内存 channel + goroutine |
| **运维复杂度** | 0 — 无新服务，无新依赖 |
| **引入价值** | 精准解决批量写入问题，不多不少 |
| **当前需求匹配** | ✅ 完美匹配 — 高频小写入合并为低频批写入 |
| **部署改动** | 无 — PhoenixA 内部新增组件 |
| **数据一致性** | 服务内保障（graceful shutdown 时 flush） |
| **故障影响** | 最多丢失 buffer 窗口内的数据（可通过 Artemis 重跑恢复） |

### 2.3 结论

**推荐：PhoenixA 内置 Write Buffer，不引入 Kafka + Flink。**

理由：
1. **当前不是流处理场景**。cronjob 调度 Artemis 是纯批处理，Kafka+Flink 的 exactly-once、event time window 等能力用不上。
2. **资源紧张**。预留的 16GB RAM 是唯一缓冲区，Kafka+Flink 用掉后无法再给 VM1/VM2 扩容。
3. **运维代价不匹配收益**。两个人维护 6 个服务已经很吃力，再加 2 个有状态中间件维护成本过高。
4. **按架构文档规划**，Kafka+Flink 的触发条件是 "当需要实时事件流处理（如实时新闻 → 实时影响分析）时再引入"，当前不满足。
5. **PhoenixA 自身完全可以解决**。Go 的 channel + goroutine 天生适合做 write buffer，无需外部依赖。

> **何时需要 Kafka + Flink？**
> - Atlas 需要实时新闻事件流 → 实时影响分析 → 实时推送
> - 分钟级行情需要实时写入 + 实时因子计算
> - 多数据源需要统一的事件总线做恰好一次语义  
> → 这些场景预计在 Phase F 阶段，当前不需要。

---

## 三、PhoenixA Write Buffer 详细设计

### 3.1 架构概览

```
                        PhoenixA 进程内部
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  HTTP Request                                                   │
│  POST /api/v2/bars/.../upsert                                  │
│       │                                                         │
│       ▼                                                         │
│  BarsController.Upsert()                                        │
│       │                                                         │
│       ├── len(bars) >= directFlushThreshold?                    │
│       │       YES → 直接走 BarsService.BatchUpsert() (现有路径)  │
│       │       NO  ↓                                             │
│       │                                                         │
│       ▼                                                         │
│  WriteBufferManager.Submit(bufferKey, bars)                     │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────── per-key channel ────────────┐                    │
│  │  bufferKey = "{table}:{period}:{adjust}" │                    │
│  │                                          │                    │
│  │  bars_item ──→ channel (cap: 8192)       │                    │
│  │                    │                     │                    │
│  │                    ▼                     │                    │
│  │  flush goroutine (per key)               │                    │
│  │  ├── 条件1: len(buffer) >= maxBatchSize  │                    │
│  │  ├── 条件2: ticker >= flushInterval     │                    │
│  │  └── 条件3: shutdown signal              │                    │
│  │         │                                │                    │
│  │         ▼                                │                    │
│  │  BarsDao.BatchUpsert(merged_bars)        │                    │
│  └──────────────────────────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件：WriteBufferManager

```go
// internal/buffer/write_buffer.go

type WriteBufferManager struct {
    *core.BaseComponent

    mu       sync.RWMutex
    buffers  map[string]*tableBuffer  // key → per-table buffer

    cfg      WriteBufferConfig
}

type WriteBufferConfig struct {
    MaxBatchSize          int           // 达到此行数立即 flush (default: 2000)
    FlushInterval         time.Duration // 定时 flush 间隔 (default: 3s)
    DirectFlushThreshold  int           // 单次请求 >= 此行数直接写 DB (default: 500)
    ChannelSize           int           // per-key channel 容量 (default: 8192)
    ShutdownTimeout       time.Duration // graceful shutdown 等待 (default: 10s)
}
```

### 3.3 per-key Buffer

```go
type tableBuffer struct {
    key       string              // e.g. "bars_stock_zh_a_daily_nf"
    ch        chan []*model.StandardBar
    dao       *dao.BarsDao
    cfg       WriteBufferConfig
    wg        sync.WaitGroup
    cancel    context.CancelFunc
    flushed   atomic.Int64        // metrics: total flushed rows
    submitted atomic.Int64        // metrics: total submitted rows
}
```

每个 `bufferKey` 对应一个 `tableBuffer`，拥有独立的 channel 和 flush goroutine。
这样不同表（不同 period/adjust 组合）的写入互不阻塞。

### 3.4 Flush 策略

```
flush 触发条件（任一满足即触发）：

1. 批量满：累积行数 >= MaxBatchSize (2000)
   → 适用于首次全量拉取（子任务快速连续提交）

2. 定时器：距上次 flush >= FlushInterval (3s)
   → 适用于日常更新（低频但持续的小写入）
   → 保证最大延迟不超过 3 秒

3. Shutdown：收到停止信号
   → graceful shutdown 时 drain channel 并 flush 剩余数据
```

### 3.5 直接写入 vs 缓冲写入 策略

```
单次请求 bars 数量:

  >= DirectFlushThreshold (500)  →  绕过 buffer，直接 BatchUpsert
                                    （首次全量拉取时每个 symbol 有上千行，
                                      不需要再聚合，直接写效率最高）

  < DirectFlushThreshold (500)   →  Submit 到 WriteBuffer
                                    （日常更新时每个 symbol 只有 1-几行，
                                      聚合后批量写更高效）
```

### 3.6 Controller 层改动

```go
// BarsController.Upsert() — 修改后

func (c *BarsController) Upsert(w http.ResponseWriter, r *http.Request) {
    // ... 现有参数解析 ...

    bars := parseBars(req.Bars)

    if len(bars) >= c.BufferMgr.DirectFlushThreshold() {
        // 大批量：直接写（现有路径）
        if err := c.Svc.BatchUpsert(ctx, q, req.Bars); err != nil {
            writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
            return
        }
    } else {
        // 小批量：提交到 write buffer
        bufferKey := dao.BarsTableName(q.AssetType, q.Market, q.Period, q.Adjust)
        if err := c.BufferMgr.Submit(ctx, bufferKey, q, bars); err != nil {
            writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "buffer full"})
            return
        }
    }

    // ext 数据处理不变（ext 通常量小且不频繁，不需要 buffer）
    if len(req.Ext) > 0 && req.Meta.Source != "" {
        if err := c.Svc.BatchUpsertExt(ctx, req.Meta.Source, q, req.Ext); err != nil {
            logging.Errorf(ctx, "bars ext upsert error: %s", err.Error())
        }
    }

    writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}
```

### 3.7 生命周期管理

WriteBufferManager 作为一个 infra Component 注册到 PhoenixA 的生命周期中：

```go
// Start: 启动时不创建任何 buffer（按需懒创建）
func (m *WriteBufferManager) Start(ctx context.Context) error {
    return m.BaseComponent.Start(ctx)
}

// Stop: graceful shutdown
func (m *WriteBufferManager) Stop(ctx context.Context) error {
    m.mu.RLock()
    buffers := make([]*tableBuffer, 0, len(m.buffers))
    for _, b := range m.buffers {
        buffers = append(buffers, b)
    }
    m.mu.RUnlock()

    // 通知所有 buffer 停止接收
    for _, b := range buffers {
        b.cancel()
    }

    // 等待所有 buffer flush 完成（带超时）
    done := make(chan struct{})
    go func() {
        for _, b := range buffers {
            b.wg.Wait()
        }
        close(done)
    }()

    select {
    case <-done:
        logging.Info(ctx, "WriteBufferManager: all buffers flushed")
    case <-time.After(m.cfg.ShutdownTimeout):
        logging.Warn(ctx, "WriteBufferManager: shutdown timeout, some data may be lost")
    }

    return m.BaseComponent.Stop(ctx)
}
```

### 3.8 Metrics & 可观测性

每个 tableBuffer 暴露指标，通过 PhoenixA 的 health/metrics 端点查看：

| 指标 | 说明 |
|------|------|
| `buffer_submitted_total` | 累计提交行数 |
| `buffer_flushed_total` | 累计写入 DB 行数 |
| `buffer_pending` | 当前 channel 中待写行数 |
| `buffer_flush_count` | flush 次数 |
| `buffer_flush_duration_ms` | 最近一次 flush 耗时 |
| `buffer_last_flush_time` | 最近一次 flush 时间 |

### 3.9 Ext 数据的处理

当前 `bars_ext_*` 写入场景和 bars 相同（每个 child 都会调用），但 ext 数据行数与 bars 完全一致。
因此 WriteBufferManager 也应支持 ext 的缓冲写入。

设计上有两种方案：
- **方案 A**：bars 和 ext 分别有独立的 buffer → 简单但可能不同步
- **方案 B**：Submit 时将 bars + ext 打包一起提交，flush 时一起写 → 保证一致性

**推荐方案 B**：将 Submit 的数据结构设计为包含 bars + ext + metadata，flush 时先写 bars 再写 ext。

---

## 四、性能预期

### 4.1 每日增量更新

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| HTTP 请求数（Artemis → PhoenixA） | ~5000 | ~5000（不变） |
| DB 事务数 | **~5000** | **~3-5**（5000 行 ÷ 2000/batch） |
| DB commit 数 | **~5000** | **~3-5** |
| 总写入行数 | ~5000 | ~5000（不变） |
| 预估写入耗时 | ~5000 × ~5ms = ~25s | ~3 × ~10ms = ~30ms |
| 写入延迟（数据可见） | 即时（每 symbol 立即 commit） | 最大 3s（flush interval） |

### 4.2 首次全量拉取

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| HTTP 请求数 | ~5000 | ~5000（不变） |
| 路径 | BatchUpsert 直接写 | **绕过 buffer 直接写**（≥500 行） |
| DB 事务数 | ~5000 | ~5000（不变，本来就是大批量） |

→ 全量拉取场景不受影响，因为每个 symbol 有上千行，直接走 `DirectFlush` 路径。

---

## 五、与 Artemis 侧的关系

### 5.1 Artemis 需要改动吗？

**不需要。**

PhoenixA 的 Write Buffer 对 Artemis 完全透明：
- API 接口不变（`POST /api/v2/bars/.../upsert`）
- 请求/响应格式不变
- Artemis 仍然按 symbol 逐个调用 PhoenixA

### 5.2 为什么不在 Artemis 侧聚合？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Artemis 父任务聚合** | 减少 HTTP 请求数 | OrchestratorUnit 需要大改；内存压力（5000 symbol 的数据全放内存）；与现有 child sink 模型冲突 |
| **PhoenixA 写缓冲** | Artemis 零改动；对所有调用方生效（不只 Artemis）；数据在 PhoenixA 侧聚合更安全 | 数据可见延迟 ≤ 3s |

**选择 PhoenixA 侧缓冲**：
1. 改动集中在一个服务，不影响 Artemis 的任务编排模型
2. 未来其他服务（Atlas 等）写 bars 也自动受益
3. OrchestratorUnit 现在是顺序执行 children，改为聚合模式需要重构 `_execute_strategy`

### 5.3 长期演进

如果未来要进一步优化 HTTP 请求数（从 5000 减少到几十次），可以在 Artemis 侧做：
- OrchestratorUnit 支持 "有界聚合" sink_mode（每 N 个 child 聚合一次提交）
- 或者引入 gRPC streaming（Artemis → PhoenixA 建立流式连接，连续发送 bars）

但这些是后续优化，当前 PhoenixA 侧 buffer 已经解决了 DB 压力的核心问题。

---

## 六、配置

在 `phoenixA/config/config.yaml` 中新增：

```yaml
biz_config:
  write_buffer:
    enabled: true
    max_batch_size: 2000          # 行数达到此值立即 flush
    flush_interval: 60s            # 定时 flush 间隔
    direct_flush_threshold: 500   # 单次请求 >= 此行数直接写 DB
    channel_size: 8192            # per-key channel 容量
    shutdown_timeout: 10s         # graceful shutdown 等待时间
```

当 `write_buffer.enabled = false` 时，所有写入走现有直接路径，行为完全不变。

---

## 七、实施计划

| 阶段 | 工作项 | 预估工时 |
|------|--------|---------|
| 1 | 实现 `WriteBufferManager` 组件 + `tableBuffer` + flush goroutine | 1-2 天 |
| 2 | 修改 `BarsController.Upsert()` 接入 buffer | 0.5 天 |
| 3 | 添加配置解析（`WriteBufferConfig`） | 0.5 天 |
| 4 | 生命周期注册（Component 注册 + graceful shutdown） | 0.5 天 |
| 5 | Metrics 暴露 + 日志 | 0.5 天 |
| 6 | 单元测试 + 集成测试 | 1 天 |
| **总计** | | **~4-5 天** |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| PhoenixA 崩溃导致 buffer 数据丢失 | 最多丢失 flush_interval 窗口内的数据 | Artemis 任务可重跑（基于 last_update_date 幂等）；生产环境 PhoenixA 很少崩溃 |
| Channel 满导致请求阻塞 | 写入方（Artemis）超时 | channel_size=8192 足够大；超出时返回 503 让 Artemis 重试 |
| Flush 失败（DB 不可用） | buffer 持续积压 | 重试 + 限制 channel 深度 + 告警 |
| 不同 symbol 相同 key 的并发写入 | 无风险 — channel 串行化了写入 | GORM 的 `ON CONFLICT DO UPDATE` 保证幂等 |

---

## 附录：决策记录

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| 1 | PhoenixA 内置 Write Buffer，不引入 Kafka + Flink | 批处理场景不需要流处理中间件；资源和运维代价过高 | 2026-05-07 |
| 2 | Kafka + Flink 预留给 Phase F（实时事件流场景） | 保持架构文档一致性，16GB RAM 留给真正需要的场景 | 2026-05-07 |
| 3 | Buffer 在 PhoenixA 侧而非 Artemis 侧 | 一处改动全局受益；不破坏 Artemis 任务编排模型 | 2026-05-07 |
| 4 | 大批量直接写、小批量走 buffer | 全量拉取不需要聚合（本身就够大），日常更新需要 | 2026-05-07 |

