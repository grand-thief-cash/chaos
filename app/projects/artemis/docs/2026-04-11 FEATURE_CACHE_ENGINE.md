# Cache Engine Design

> Date: 2026-04-11
> Status: REVIEWED (已确认，待开发)
> Scope: Artemis Cache Layer — 为 Workbench 提供本地 Arrow 缓存，减少 PhoenixA 重复调用

---

## 1. 背景与动机

### 1.1 当前问题

当前 Artemis Workbench 的每一次操作（获取行情、计算指标、执行回测）都直接调用 PhoenixA：

```
Workbench API → market_data.get_market_bars() → PhoenixAClient → HTTP → PhoenixA(Go) → MySQL/ClickHouse
```

策略研发过程中，用户会反复操作相同标的、相同时间段的数据：
- 调整策略参数后重新回测 → 重拉同一批 K 线
- 切换指标组合 → 重拉同一批 K 线
- 微调日期范围 → 大部分数据重复拉取

每次请求都要经过 HTTP → PhoenixA → DB 查询链路，延迟高、PhoenixA 压力大。

### 1.2 目标

在 Artemis 内部增加本地 Cache Layer，用 Apache Arrow + mmap 实现零拷贝列式缓存：

```
               PhoenixA (Go)
              ┌──────┬───────┐
              │MySQL │ClickHouse│
              └──────┴───────┘
                     │  (cache miss 时回源)
                     ↓
            ┌─────────────────┐
            │  Artemis Cache  │  ← Arrow 文件 + mmap
            │  Engine         │
            └────────┬────────┘
                     │  (cache hit 直接读本地)
                     ↓
           Strategy / Workbench
```

**核心收益：**
- 回测/指标计算场景，热点数据读取延迟从网络级降到磁盘级
- 减少 PhoenixA 负载
- 支持离线策略研发（缓存过的数据不需要网络）

---

## 2. 架构设计

### 2.1 模块位置

```
artemis/
├── engines/
│   ├── cache_engine/            ← NEW
│   │   ├── __init__.py
│   │   ├── cache_engine.py      # 核心入口 CacheEngine
│   │   ├── partition.py         # 分区解析 PartitionResolver + PartitionRule
│   │   ├── storage.py           # Arrow 文件读写 ArrowStorage
│   │   ├── compaction.py        # 增量合并 CompactionManager
│   │   ├── index.py             # 缓存索引 CacheIndex
│   │   └── lru.py               # LRU 淘汰 LRUEviction
│   ├── strategy_engine/
│   └── ...
├── services/workbench/
│   ├── market_data.py           ← 修改：接入 cache
│   └── backtest.py              ← 修改：接入 cache
└── models/configs.py            ← 修改：增加 CacheEngineCfg
```

### 2.2 核心组件关系

```
┌─────────────────────────────────────────────────────────┐
│                      CacheEngine                         │
│                                                         │
│  ┌──────────────────┐   ┌───────────────────────────┐  │
│  │ PartitionResolver │   │      ArrowStorage          │  │
│  │                  │   │                           │  │
│  │ resolve_files()  │   │ read_mmap() / write()     │  │
│  │ resolve_dir()    │   │ merge() / delete()        │  │
│  └──────────────────┘   └───────────────────────────┘  │
│                                                         │
│  ┌──────────────────┐   ┌───────────────────────────┐  │
│  │   CacheIndex     │   │    LRUEviction             │  │
│  │                  │   │                           │  │
│  │ record_access()  │   │ check_and_evict()         │  │
│  │ get_stats()      │   │ get_eviction_candidates() │  │
│  └──────────────────┘   └───────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              CompactionManager                    │   │
│  │  compact_symbol() / compact_all()                │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.3 数据流

**读取（cache hit）：**
```
CacheEngine.get(symbol, period, start, end, ...)
  → PartitionResolver.resolve_files() → 定位 Arrow 文件列表
  → ArrowStorage.read_mmap() → 零拷贝读取
  → concat + 时间切片
  → 返回 pd.DataFrame
```

**读取（cache miss）：**
```
CacheEngine.get(...)
  → PartitionResolver.resolve_files() → 发现缺失
  → 调用 data_fetcher (PhoenixAClient) 回源拉取
  → ArrowStorage.write() → 写入 Arrow 文件
  → CacheIndex.record_access() → 更新索引
  → 返回数据
```

> **补充说明（2026-04-13）**：本文中的 `CacheIndex` / SQLite 索引，与后续 refactor 中提出的 `coverage-aware cache` 不是同一件事。
>
> - `CacheIndex` / SQLite：负责持久化缓存元数据（文件、大小、日期范围、访问记录等）
> - `coverage-aware cache`：负责判断缓存是否完整、是否需要 backfill、如何规划缺失区间回源
>
> 推荐关系是：coverage-aware cache 建立在 CacheIndex 之上，但它们分属不同层次。

---

## 3. 分区规则设计 (Partition Rules)

### 3.1 核心思路

不同数据类型 + 周期需要不同的文件粒度：
- 日线数据：一年约 244 条，按 **年** 分区足够
- 分钟线数据：一年约 60k 条，按 **月** 分区更合理
- Index 数据：与 stock 类似但 asset_type 不同

分区由规则驱动，规则是可配置的策略：

```yaml
engine:
  cache_engine:
    partition_rules:
      - match:
          asset_type: "stock"
          period: "daily"
        granularity: "yearly"      # 按年分文件
        # 生成路径: stock/{market}/{period}/{adjust}/{symbol}/{year}.arrow

      - match:
          asset_type: "stock"
          period: "1min"
        granularity: "monthly"     # 按月分文件
        # 生成路径: stock/{market}/{period}/{adjust}/{symbol}/{year}_{month}.arrow

      - match:
          asset_type: "index"
          period: "daily"
        granularity: "yearly"
        # 生成路径: index/{market}/{period}/{adjust}/{symbol}/{year}.arrow

      # 兜底规则：未匹配时默认
      - match: {}
        granularity: "yearly"
```

### 3.2 路径生成逻辑

每条 `PartitionRule` 包含：

| 字段 | 说明 |
|------|------|
| `match` | 匹配条件 dict，支持 `asset_type`, `market`, `period`, `adjust` |
| `granularity` | `yearly` 或 `monthly` |
| `path_template` | 可选自定义模板，不提供时使用默认模板 |

**默认模板（granularity=yearly）：**
```
{asset_type}/{market}/{period}/{adjust}/{symbol}/{year}.arrow
```

**默认模板（granularity=monthly）：**
```
{asset_type}/{market}/{period}/{adjust}/{symbol}/{year}_{month:0>2}.arrow
```

### 3.3 示例

| asset_type | market | period | adjust | symbol | 日期 | 生成路径 |
|---|---|---|---|---|---|---|
| stock | zh_a | daily | hfq | 000001 | 2025全年 | `stock/zh_a/daily/hfq/000001/2025.arrow` |
| stock | zh_a | 1min | hfq | 000001 | 2025-01 | `stock/zh_a/1min/hfq/000001/2025_01.arrow` |
| index | zh_a | daily | nf | 000300 | 2025全年 | `index/zh_a/daily/nf/000300/2025.arrow` |
| stock | zh_a | weekly | hfq | 600036 | 2025全年 | `stock/zh_a/weekly/hfq/600036/2025.arrow` |

### 3.4 Resolve 文件列表（范围查询）

查询 `start_date` 到 `end_date` 时，PartitionResolver 根据 granularity 计算需要读取哪些文件：

```
查询: symbol=000001, period=daily, start=2024-06-15, end=2025-06-16
granularity=yearly → 文件列表:
  - stock/zh_a/daily/hfq/000001/2024.arrow  (切片 2024-06-15 ~ 2024-12-31)
  - stock/zh_a/daily/hfq/000001/2025.arrow  (切片 2025-01-01 ~ 2025-06-16)
```

```
查询: symbol=000001, period=1min, start=2020-01-01, end=2020-03-01
granularity=monthly → 文件列表:
  - stock/zh_a/1min/hfq/000001/2020_01.arrow
  - stock/zh_a/1min/hfq/000001/2020_02.arrow
  - stock/zh_a/1min/hfq/000001/2020_03.arrow  (切片到 03-01)
```

---

## 4. 数据写入与增量管理

### 4.1 写入场景

1. **首次拉取（全量写入）**：从 PhoenixA 拉取 `2020-01-01 ~ 2025-12-31` 日线数据
   → 写入 `2020.arrow`, `2021.arrow`, ..., `2025.arrow`

2. **增量更新（年分区）**：之后每天有新数据（如 `2026-04-13` 的日线数据）
   → 写入增量文件 `2026.inc.20260413.arrow`

3. **增量更新（月分区）**：每天也有新的分钟线数据（如 `2026-04-13` 的 1min 数据属于 `2026_04` 月分区）
   → 写入增量文件 `2026_04.inc.20260413.arrow`

### 4.2 增量文件命名

所有分区类型统一使用天级别增量文件，文件名中包含具体日期：

| 场景 | 文件名 | 说明 |
|------|--------|------|
| 年分区 Base | `2025.arrow` | 该年完整数据 |
| 年分区 Delta | `2025.inc.20260413.arrow` | 2025 年 04-13 这一日的增量数据 |
| 月分区 Base | `2026_04.arrow` | 2026 年 4 月完整数据 |
| 月分区 Delta | `2026_04.inc.20260413.arrow` | 2026 年 4 月 04-13 这一日的增量数据 |

**设计说明：**
- 年分区和月分区**统一**产生 `{base_name}.inc.{YYYYMMDD}.arrow` 增量文件，每个增量文件对应一天的数据
- `.inc.` 前缀清晰区分增量文件与 base 文件，避免歧义
- 同一个 base 可能累积多个增量文件（如 `2026_04.inc.20260413.arrow`, `2026_04.inc.20260414.arrow`）
- Compaction 合并时：按时间索引去重排序，生成新的 base 文件

### 4.3 写入逻辑

```python
def put(self, *, asset_type, market, period, adjust, symbol, data: pd.DataFrame):
    rule = self._partition_resolver.resolve_rule(asset_type, market, period)
    # 按时间分组
    groups = self._group_by_partition(data, rule.granularity)
    for partition_key, partition_df in groups:
        path = self._partition_resolver.resolve_path(...)
        # 统一逻辑：检查是否已有 base 文件
        if path.exists():
            # 写入天级别增量文件: {base_name}.inc.{YYYYMMDD}.arrow
            inc_date = partition_df["date"].max().strftime("%Y%m%d")
            inc_path = path.with_name(f"{path.stem}.inc.{inc_date}.arrow")
            self._storage.append_or_create(inc_path, partition_df)
        else:
            # 首次：直接写 base
            self._storage.write(path, partition_df)
```

---

## 5. Compaction（增量合并）

### 5.1 触发方式

由 CronJob 定时触发，通过 HTTP API 调用（当前仅支持 API 触发，是否自动触发待定）：

```
POST /workbench/cache/compact
Body: { "symbol": "000001", "period": "daily" }  # 可选：不传则 compact 全部
```

> **注意：** 当前阶段仅通过 API 触发 Compaction。是否需要在每次写入后自动判断是否需要 compact，待后续评估后在文档中更新。

### 5.2 Compaction 流程

```
compact(symbol, period):
    1. 扫描 symbol 目录下所有 .inc.*.arrow 文件
    2. 按 base 文件分组增量文件:
       # 例如:
       #   2025.arrow ← [2025.inc.20260413.arrow, 2025.inc.20260414.arrow]
       #   2026_04.arrow ← [2026_04.inc.20260413.arrow]
    3. 对每个 base 文件:
       base = read(base_path)
       deltas = read_all(inc_paths)   # 可能存在多个增量文件
       merged = concat([base] + deltas)
       merged = deduplicate(merged, subset="date", keep="last")
       merged = sort_by(merged, "date")
       write_atomically(base_path, merged)   # 原子写入：先写 tmp 再 rename
       delete_all(inc_paths)
    4. 更新 CacheIndex
    5. 返回 CompactionResult
```

### 5.3 Compaction 并发互斥

Compaction 与回测/实验之间存在**双向互斥**：

```
┌───────────────────────────────────────────────────────┐
│                    CompactionLock                       │
│                                                        │
│  状态: IDLE → RUNNING → IDLE                            │
│                                                        │
│  Compaction 请求:                                      │
│    如果有回测/实验正在进行 → 等待或拒绝（返回 Retry）     │
│                                                        │
│  回测/实验请求:                                        │
│    如果有 Compaction 正在进行 → 等待或拒绝（返回 Retry） │
└───────────────────────────────────────────────────────┘
```

**实现方式：** 使用一个全局 `threading.RLock` 或 `threading.Event` 作为 CompactionLock：
- Compaction 开始前检查是否有活跃的回测/实验任务，有则等待或返回 `HTTP 503 Retry-After`
- 回测/实验开始前检查是否有 Compaction 正在进行，有则等待或返回 `HTTP 503 Retry-After`
- 提供优雅降级：如果互斥等待超时，可以选择放弃 Compaction（数据仍然可读，只是多了增量文件）

### 5.4 Compaction 安全性

- **原子写入**：先写 `{base}.tmp.arrow`，写完后 `rename` 覆盖原文件，避免写坏
- **文件锁**：compaction 期间对该文件加读写锁，防止并发读写冲突
- **可中断**：如果 compaction 中断，tmp 文件残留不会影响 base 文件，下次 compact 自动清理

---

## 6. 数据查询设计

### 6.1 核心查询接口

```python
def get(
    self,
    *,
    symbol: str,
    period: str = "daily",
    start_date: str,              # "2020-01-01"
    end_date: str,                # "2020-03-01"
    asset_type: str = "stock",
    market: str = "zh_a",
    adjust: str = "nf",
    use_cache: bool = True,       # 是否使用缓存
    data_fetcher: Callable = None, # cache miss 时的回源函数
) -> pd.DataFrame:
```

### 6.2 查询流程

```
get(symbol="000001", period="daily", start="2024-05-15", end="2025-06-16")

1. PartitionResolver.resolve_files(start, end)
   → base: [2024.arrow, 2025.arrow]
   → 增量扫描: glob 2024.inc.*.arrow → 无; glob 2025.inc.*.arrow → 2025.inc.20260413.arrow, 2025.inc.20260414.arrow

2. 检查文件存在性:
   - 2024.arrow ✓
   - 2024 的增量文件 ✗ (无增量)
   - 2025.arrow ✓
   - 2025.inc.20260413.arrow ✓
   - 2025.inc.20260414.arrow ✓

3. 读取:
   tables = []
   tables += read_mmap(2024.arrow)
   tables += read_mmap(2025.arrow)
   tables += read(2025.inc.20260413.arrow)   # 增量文件
   tables += read(2025.inc.20260414.arrow)   # 增量文件

4. 合并 + 去重:
   merged = concat(tables)
   merged = deduplicate(merged, subset="date", keep="last")
   merged = sort(merged, "date")

5. 时间切片:
   result = merged[(merged.date >= "2024-05-15") & (merged.date <= "2025-06-16")]

6. CacheIndex.record_access(key)
   LRUEviction.check_and_evict()

7. return result
```

**分钟线查询示例：**

```
get(symbol="000001", period="1min", start="2026-04-10", end="2026-04-14")

1. PartitionResolver.resolve_files(start, end)
   → base: [2026_04.arrow]
   → 增量扫描: glob 2026_04.inc.*.arrow → 2026_04.inc.20260413.arrow, 2026_04.inc.20260414.arrow

2. 检查文件存在性:
   - 2026_04.arrow ✓
   - 2026_04.inc.20260413.arrow ✓
   - 2026_04.inc.20260414.arrow ✓

3-7. 同上述流程
```

### 6.3 Cache Miss 处理

当发现文件不存在时：

```
resolve_files() 返回:
  existing: [2024.arrow, 2025.arrow]
  missing:  [2023.arrow]   ← 需要回源

如果 use_cache=False 或有 missing 文件:
  → 调用 data_fetcher(symbol, period, missing_start, missing_end)
  → 写入缓存
  → 重新读取
```

**分段回源策略：**
- 只回源缺失的时间段，不重复拉取已有的数据
- 回源后立即写入缓存

### 6.4 use_cache 标志位

| use_cache | 行为 |
|-----------|------|
| `True` | 优先读缓存，miss 时回源并缓存 |
| `False` | 完全跳过缓存，直接回源，但**仍更新缓存**（保证缓存新鲜） |

---

## 7. LRU 淘汰策略

### 7.1 配置

```yaml
engine:
  cache_engine:
    max_cache_size: "5GB"          # 缓存目录最大占用空间（软限制）
    eviction_policy: "lru"         # 目前仅支持 lru
    eviction_check_interval: 100   # 每 N 次访问检查一次是否需要淘汰
```

> **设计决策：** 不使用 TTL 过期机制。缓存新鲜度通过手动清除 + LRU 淘汰保证。LRU 淘汰允许软限制 — 缓存允许在一段时间内超出 `max_cache_size`，不需要严格执行。

### 7.2 LRU 机制

CacheIndex 维护每个 Arrow 文件的元数据：

```python
@dataclass
class CacheEntry:
    key: str                    # "stock/zh_a/daily/hfq/000001/2025"
    file_path: Path
    file_size: int              # bytes
    last_access_time: float     # timestamp
    access_count: int
    is_delta: bool              # 是否增量文件
```

淘汰流程：

```
每次 get/put 后:
  access_count += 1
  if access_count % eviction_check_interval == 0:
      current_size = total_cache_size()
      if current_size > max_cache_size:
          candidates = sorted by last_access_time (ascending)
          while current_size > max_cache_size * 0.9:   # 淘汰到 90%
              entry = candidates.pop(0)                # 最久未访问
              delete(entry.file_path)
              index.remove(entry.key)
              current_size -= entry.file_size
```

**软限制容忍度：**
- `max_cache_size` 是软限制，不是硬限制
- LRU 检查是周期性的（每 `eviction_check_interval` 次访问），在检查间隙缓存可能短暂超出限制
- 这种设计允许高并发场景下不被淘汰逻辑阻塞，保证读写优先

### 7.3 LRU 与 Compaction 的交互

- Compaction 产生的合并文件更新 CacheEntry 的 file_size
- 淘汰时优先淘汰增量文件（`is_delta=True`），因为它们可以被重新生成
- 不淘汰正在被读取的文件（通过引用计数或文件锁判断）

---

## 8. 缓存索引 (CacheIndex)

### 8.1 索引结构

使用 SQLite 作为轻量级索引存储（`cache_dir/.cache_index.db`），原因：
- 不依赖外部服务（Redis 等）
- 支持查询和排序
- 文件级持久化，重启不丢失

**表结构：**

```sql
CREATE TABLE cache_entries (
    cache_key   TEXT PRIMARY KEY,   -- "stock/zh_a/daily/hfq/000001/2025"
    file_path   TEXT NOT NULL,
    file_size   INTEGER NOT NULL,
    granularity TEXT NOT NULL,       -- "yearly" / "monthly"
    is_delta    INTEGER DEFAULT 0,
    row_count   INTEGER,
    min_date    TEXT,                -- 数据时间范围
    max_date    TEXT,
    last_access REAL NOT NULL,       -- Unix timestamp
    access_count INTEGER DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE INDEX idx_last_access ON cache_entries(last_access);
CREATE INDEX idx_cache_key_prefix ON cache_entries(cache_key);
```

### 8.2 索引操作

```python
class CacheIndex:
    def record_access(self, key: str) -> None:
        """更新 last_access_time 和 access_count"""

    def register(self, entry: CacheEntry) -> None:
        """新文件写入后注册到索引"""

    def remove(self, key: str) -> None:
        """删除文件后移除索引"""

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """查询单条索引"""

    def get_entries_by_prefix(self, prefix: str) -> List[CacheEntry]:
        """按前缀查询（用于 symbol 级别操作）"""

    def total_size(self) -> int:
        """当前缓存总大小"""

    def get_lru_candidates(self, count: int) -> List[CacheEntry]:
        """获取最久未访问的 N 个条目"""

    def get_hit_rate_stats(self) -> CacheStats:
        """命中率统计"""
```

### 8.3 索引与文件一致性

- 启动时执行 `reconcile()`：扫描磁盘文件，与索引比对
  - 索引有但文件不存在 → 删除索引条目
  - 文件存在但索引没有 → 从文件元数据重建索引条目

### 8.4 索引与 coverage-aware cache 的关系

SQLite `CacheIndex` 适合作为 coverage metadata 的默认存储后端。后续如果引入 coverage-aware cache，建议在索引层补充如下字段：

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

然后由上层：

- `CoverageResolver` 负责判断 full hit / partial hit / miss
- `BackfillPlanner` 负责规划缺失区间回源

### 8.5 Docker 部署 — 缓存目录挂载

CacheIndex（SQLite DB）和 Arrow 数据文件都位于 `cache_dir` 下。Docker 部署时需要将整个缓存目录挂载为 volume，确保数据持久化。

**docker-compose.yaml 新增 volume 挂载：**

```yaml
services:
  artemis:
    # ... 现有配置 ...
    volumes:
      - /home/machine/data_volume/artemis/config:/app/config
      - /home/machine/data_volume/artemis/logs:/app/logs
      - /home/machine/data_volume/artemis/cache:/app/cache    # NEW: 缓存目录挂载
```

**deploy_artemis.py 修改：**
- `upload_files()` 中需要上传 config-production.yaml 时，确保 cache_engine.cache_dir 配置为容器内路径 `/app/cache/artemis`
- 生产环境的 `config-production.yaml` 中 `cache_dir` 设置为绝对路径 `/app/cache/artemis`（容器内路径），通过 volume 映射到宿主机

**开发环境：** `cache_dir` 使用项目相对路径 `./cache/artemis`。

---

## 9. 并发控制

### 9.1 读写锁

```python
# 每个文件一个读写锁（file_path → RWLock）
# 读操作（get）：获取读锁，允许多个并发读
# 写操作（put/compact）：获取写锁，互斥

class FileLockManager:
    def acquire_read(self, path: Path) -> FileReadGuard: ...
    def acquire_write(self, path: Path) -> FileWriteGuard: ...
```

### 9.2 防止重复下载（Stampede Protection）

```python
# 当多个请求同时 miss 同一个文件时，只允许第一个请求去回源
# 其他请求等待第一个请求完成后直接读缓存

class LoadingGuard:
    _loading: Dict[str, threading.Event] = {}

    def acquire(self, key: str) -> Optional[threading.Event]:
        """返回 None 表示获得加载权，返回 Event 表示需要等待"""

    def release(self, key: str) -> None:
        """加载完成后通知等待者"""
```

---

## 10. 配置结构

### 10.1 config.yaml 新增

```yaml
engine:
  cache_engine:
    enabled: true
    cache_dir: "./cache/artemis"        # 缓存根目录（开发环境用项目相对路径，生产环境在 config-production.yaml 中配置绝对路径）
    max_cache_size: "5GB"               # 最大缓存空间（软限制）
    eviction_policy: "lru"              # 淘汰策略
    eviction_check_interval: 100        # 每N次访问检查一次淘汰
    default_asset_type: "stock"         # 默认资产类型
    default_market: "zh_a"              # 默认市场
    default_adjust: "nf"                # 默认复权方式
    partition_rules:                    # 分区规则列表
      - match:
          asset_type: "stock"
          period: "daily"
        granularity: "yearly"
      - match:
          asset_type: "stock"
          period: "weekly"
        granularity: "yearly"
      - match:
          asset_type: "stock"
          period: "1min"
        granularity: "monthly"
      - match:
          asset_type: "stock"
          period: "5min"
        granularity: "monthly"
      - match:
          asset_type: "stock"
          period: "15min"
        granularity: "monthly"
      - match:
          asset_type: "stock"
          period: "30min"
        granularity: "monthly"
      - match:
          asset_type: "stock"
          period: "60min"
        granularity: "monthly"
      - match:
          asset_type: "index"
        granularity: "yearly"
      - match: {}                       # 兜底规则
        granularity: "yearly"
```

### 10.2 Pydantic 模型新增

```python
class PartitionRuleCfg(BaseModel):
    match: Dict[str, str] = Field(default_factory=dict)
    granularity: str = "yearly"  # "yearly" | "monthly"

class CacheEngineCfg(BaseModel):
    enabled: bool = False
    cache_dir: str = "./cache/artemis"
    max_cache_size: str = "5GB"
    eviction_policy: str = "lru"
    eviction_check_interval: int = 100
    default_asset_type: str = "stock"
    default_market: str = "zh_a"
    default_adjust: str = "nf"
    partition_rules: List[PartitionRuleCfg] = Field(default_factory=list)

class EngineCfg(BaseModel):
    task_engine: TaskEngineCfg = Field(default_factory=TaskEngineCfg)
    cache_engine: CacheEngineCfg = Field(default_factory=CacheEngineCfg)  # NEW
```

---

## 11. API 接口

### 11.1 新增 Workbench Cache API

```python
# workbench_routes.py 新增

@router.post("/cache/compact")
async def compact_cache(body: CompactRequest | None = None):
    """触发缓存 Compaction"""
    # body 可选传 symbol/period 指定范围

@router.get("/cache/stats")
async def cache_stats():
    """获取缓存统计信息"""

@router.delete("/cache/entry")
async def delete_cache_entry(symbol: str, period: str, asset_type: str = "stock"):
    """手动清除指定缓存"""

@router.delete("/cache/clear")
async def clear_cache():
    """清空全部缓存"""
```

### 11.2 现有接口变更

**`GET /workbench/market-data`** 新增 `use_cache` 参数：

```
GET /workbench/market-data?symbol=000001&start_date=2024-01-01&end_date=2025-12-31&use_cache=true
```

**`POST /workbench/run`** WorkbenchRunReq 新增 `use_cache` 字段。

---

## 12. 集成方式

### 12.1 CacheEngine 初始化

CacheEngine 作为单例在应用启动时初始化，挂载到全局或通过 cfg_mgr 访问：

```python
# cache_engine/__init__.py
from artemis.core import cfg_mgr

_cache_engine: Optional[CacheEngine] = None

def get_cache_engine() -> Optional[CacheEngine]:
    global _cache_engine
    cfg = cfg_mgr.engine_config()
    if cfg and hasattr(cfg, 'cache_engine') and cfg.cache_engine.enabled:
        if _cache_engine is None:
            _cache_engine = CacheEngine(cfg.cache_engine)
        return _cache_engine
    return None
```

### 12.2 Workbench Service 改造

**market_data.py** 改造：

```python
def get_market_bars(*, symbol, start_date, end_date, period, adjust, source, use_cache=True):
    cache = get_cache_engine()
    if cache and use_cache:
        result = cache.get(
            symbol=symbol, period=period,
            start_date=start_date, end_date=end_date,
            adjust=adjust,
            data_fetcher=lambda: _fetch_from_phoenix(source, symbol, start_date, end_date, period, adjust),
        )
        if result is not None:
            return _df_to_response(result, symbol, period, start_date, end_date)

    # fallback: 直接调 PhoenixA（原逻辑不变）
    client = _build_phoenix_client(source=source)
    bars = client.get_strategy_market_bars(...)
    ...
```

---

## 13. 分阶段实施计划

### Phase 1 — 核心缓存（已确认，优先开发）

**目标：** CacheEngine 基本可用，Workbench 能走缓存

| 组件 | 内容 |
|------|------|
| CacheEngineCfg | Pydantic 模型 + config.yaml 配置 |
| PartitionResolver | 分区规则匹配 + 文件路径生成 + 范围 resolve |
| ArrowStorage | Arrow 文件 mmap 读取 + 写入 + 合并 |
| CacheEngine.get/put | 核心读写流程，cache miss 回源 |
| Workbench 集成 | market_data.py + backtest.py 接入缓存 |
| CompactionManager | 增量合并基础实现 |
| Compaction API | POST /workbench/cache/compact |
| Docker 部署 | docker-compose.yaml 新增 cache volume 挂载 |

**依赖新增：** `pyarrow`

### Phase 2 — 智能缓存增强 + 缓存清理

| 组件 | 内容 |
|------|------|
| CacheIndex (SQLite) | 文件级索引 + 持久化 |
| LRUEviction | 基于索引的 LRU 淘汰（软限制，允许超限容忍） |
| CacheClean | 缓存清理机制（手动清除 + 超限自动淘汰），区别于 Compaction |
| LoadingGuard | 并发防重复下载 |
| 命中率统计 | hit/miss/eviction 计数 |
| Cache Stats API | GET /workbench/cache/stats |
| 缓存清理 API | DELETE /workbench/cache/entry, DELETE /workbench/cache/clear |
| 启动 reconcile | 磁盘-索引一致性校验 |
| 自动 Compaction | 评估写入后是否自动触发 compact（待定） |

---

## 14. 设计优化建议

以下是我对原始需求的优化建议，供 Review 时讨论：

### 14.1 增量文件命名使用天级别粒度

**已确认：** 增量数据以天级别粒度更新，文件名格式为 `{year}.inc.{YYYYMMDD}.arrow`（如 `2026.inc.20260413.arrow`）。
- 语义清晰，一眼看出是增量文件及其日期
- 不与月分区文件名冲突
- 同一年可有多个增量文件，Compaction 时 glob 扫描 `.inc.*.arrow` 合并
- 合并时按时间索引去重排序

### 14.2 年分区与月分区统一增量机制

年分区和月分区统一使用 `{base_name}.inc.{YYYYMMDD}.arrow` 天级别增量文件。无论是日线数据（年分区）还是分钟线数据（月分区），每天新增的数据都写入对应的增量文件，Compaction 时统一合并去重。

### 14.3 Compaction 与回测/实验双向互斥

**已确认：** Compaction 与回测/实验之间需要双向互斥：
- Compaction 进行中，阻止回测和实验启动
- 回测/实验进行中，阻止 Compaction 启动
- 实现方式：全局 CompactionLock，等待或返回 Retry

### 14.4 回源函数设计

CacheEngine 不应该直接依赖 PhoenixAClient，而是通过 callback 注入：

```python
cache.get(
    ...,
    data_fetcher=lambda symbol, period, start, end: phoenix_client.get_strategy_market_bars(...)
)
```

这样 CacheEngine 保持通用性，未来可以缓存任何数据源的数据。

### 14.5 Arrow vs IPC vs Feather 格式选择

- `Arrow IPC (file format)` — 支持 mmap，适合本场景
- `Feather (v2)` — 本质上就是 Arrow IPC，pandas 原生支持
- `Parquet` — 压缩率好但不支持 mmap 零拷贝

**建议使用 Arrow IPC (.arrow)**，与用户需求一致。文件扩展名用 `.arrow`。

---

## 15. 已确认的决策

以下问题已讨论并确认：

| # | 问题 | 决策 |
|---|------|------|
| 1 | 增量文件命名 | 使用 `{year}.inc.{YYYYMMDD}.arrow` 天级别粒度（如 `2026.inc.20260413.arrow`） |
| 2 | Phase 划分 | Phase 1 足够 MVP，优先开发 |
| 3 | 缓存过期策略 | **不需要 TTL 过期机制**。使用手动清除 + LRU 淘汰，允许软限制（缓存可短暂超出大小限制） |
| 4 | Cache Clean | Phase 2 增加独立的 CacheClean 机制，与 Compaction 分离 |
| 5 | 索引存储 | 使用 SQLite |
| 6 | 并发模型 | 详见下方 15.1 说明 |
| 7 | Compaction 触发 | 当前仅通过 CronJob API 触发，是否自动触发待定 |
| 8 | cache_dir 位置 | 开发环境使用项目相对路径 `./cache/artemis`；生产环境在 `config-production.yaml` 中配置绝对路径（容器内 `/app/cache/artemis`，通过 Docker volume 挂载到宿主机） |
| 9 | Compaction 与回测互斥 | 双向互斥：Compaction 进行中阻止回测，回测进行中阻止 Compaction |
| 10 | Docker 部署 | docker-compose.yaml 新增 cache volume 挂载，deploy_artemis.py 同步更新 |

### 15.1 并发模型说明

**背景：** 当前 Artemis 使用 **线程模型**（非 async），task_engine 基于 `threading` 实现并发任务处理。

**这意味着什么：**

```
当前 Artemis 运行模型：
┌──────────────────────────────────────────┐
│  主线程 (FastAPI/uvicorn)                  │
│    ├── HTTP 请求处理 (async)               │
│    └── 调用 task_engine 提交任务            │
│                                          │
│  task_engine 线程池                        │
│    ├── Worker Thread 1 → 回测任务 A        │
│    ├── Worker Thread 2 → 回测任务 B        │
│    └── Worker Thread 3 → Compaction 任务   │
│                                          │
│  共享资源: CacheEngine, Arrow 文件          │
│    → 需要线程安全保护 (Lock/RWLock)         │
└──────────────────────────────────────────┘
```

**对 CacheEngine 的影响：**
- 多个线程可能同时调用 `CacheEngine.get()` 或 `CacheEngine.put()` — **需要读写锁保护 Arrow 文件**
- Compaction 在 task_engine 线程中执行，与回测线程并发运行 — **需要 CompactionLock 互斥**
- SQLite 索引需要设置 `check_same_thread=False` 以支持多线程访问

**是否需要改为 async？**
- 短期内不需要。CacheEngine 的瓶颈在磁盘 I/O（mmap 读取），不在线程切换开销
- FastAPI 的 async handler 调用同步的 CacheEngine 方法时，会自动放到线程池执行（`await run_in_executor`）
- 如果未来 CacheEngine 成为性能瓶颈，可以考虑改为 async，但 Phase 1 不需要
