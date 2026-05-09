# PhoenixA 存储分层规划

> 本文档规划 PhoenixA 管理的所有数据表在 **2TB M.2 NVMe（热存储）** 和 **8TB SATA SSD（温存储）** 之间的分配策略。
>
> 基于 [INFRASTRUCTURE_AND_DATA_ENGINE.md](../../../docs/2026-04-29%20INFRASTRUCTURE_AND_DATA_ENGINE.md) §4 的数据量估算，细化到每张表/每种数据类型的存储位置决策。
>
> **创建日期**：2026-05-09  
> **修订日期**：2026-05-09 (v2 — 修正因子数据量估算、简化分层策略)

---

## 〇、核心设计原则

经过对实际因子目录（372+ 因子，未来持续扩展）和数据增长趋势的评估，确定以下**核心原则**：

1. **SATA SSD 550 MB/s 对个人使用足够快** — 不需要为了性能把所有数据放 NVMe
2. **避免数据搬迁** — 如果数据会增长到需要迁移，**从一开始就放大容量盘**，不做后续搬迁
3. **NVMe 只放真正需要低延迟随机读的小数据** — 元数据、KG 向量（KNN 搜索）、安全余量
4. **大数据量 + 持续增长的数据一律放 8TB SATA** — 因子、行情、回测、行业权重
5. **留足 buffer** — 预估按 2-3x 实际需求留空间，考虑未来集成更多金融数据源

---

## 一、存储层级定义

| 层级 | 硬件 | PostgreSQL 表空间 | 路径 | 特性 | 适用场景 |
|------|------|----------------|------|------|---------|
| **Hot** | 2TB M.2 NVMe | `pg_default` | `/nvme/pgdata` | ~3500 MB/s，低延迟随机读 | 小表元数据、KNN 向量搜索、WAL |
| **Warm** | 8TB SATA SSD | `warm_storage` | `/sata8t/pgdata_warm` | ~550 MB/s，大容量 | **所有大数据量、持续增长的业务数据** |

**决策公式**：
- **数据量 < 1 GB 且不会快速增长** → NVMe
- **数据量 > 1 GB 或会持续增长** → **SATA SSD**（避免未来搬迁）
- **需要 KNN / 向量搜索的** → NVMe（随机读延迟敏感）

### 1.1 hot / warm 到底在哪里指定？

**结论：在 PostgreSQL DDL / DBA 设置里指定，不是在 `config.yaml` 里指定。**

1. **单表落盘位置**：在建表 SQL 里写
   ```sql
   CREATE TABLE ... TABLESPACE warm_storage;
   CREATE TABLE ... TABLESPACE pg_default;
   ```
2. **已有表迁移**：用
   ```sql
   ALTER TABLE ... SET TABLESPACE warm_storage;
   ```
3. **未来未显式写 TABLESPACE 的新表**：由 DBA 决定是否执行
   ```sql
   ALTER DATABASE chaos_db SET default_tablespace = warm_storage;
   -- 或
   ALTER ROLE chaos_app SET default_tablespace = warm_storage;
   ```

`config.yaml` 只是连接 PostgreSQL，不决定表落在哪块盘上；因此**不需要新增 hot/warm 配置字段**。

---

## 二、因子数据量重新估算

> 已有因子目录：**372 因子**（10 大类：技术/情绪/基本面/动量/波动/流动性/成长/质量/价值/规模）  
> 未来扩展：预计 **500-2000+ 因子**（自定义因子、组合因子、衍生因子）

### 日频因子数据量估算

```
当前 372 因子：
  5000 股 × 372 因子 × 250 天/年 = 4.65 亿行/年
  每行 ~60 bytes → ~28 GB/年（未压缩）
  TimescaleDB 压缩 (15x) → ~1.9 GB/年
  10 年累计 → ~19 GB (压缩后)

扩展到 1000 因子：
  5000 × 1000 × 250 = 12.5 亿行/年
  压缩后 → ~5 GB/年 → 10 年 ~50 GB

扩展到 2000 因子（含港股/美股）：
  15000 × 2000 × 250 = 75 亿行/年
  压缩后 → ~30 GB/年 → 10 年 ~300 GB

加上因子相关性矩阵、截面统计等衍生数据：
  → 因子域总量可能达到 100-500 GB (10 年，压缩后)
```

**结论：因子数据必须从一开始就放 8TB SATA SSD（不搬迁）。**

---

## 三、表级存储分配（完整映射 v2）

### 3.1 放 NVMe（热存储）— 仅小表和随机读密集型

| 表名 | 存储层 | 估算大小 | 理由 |
|------|--------|---------|------|
| `security_registry` | **Hot (NVMe)** | < 0.1 GB | 基础元数据，所有查询的 JOIN 源 |
| `taxonomy_category` | **Hot (NVMe)** | < 0.1 GB | 小表 |
| `taxonomy_security_map` | **Hot (NVMe)** | < 0.1 GB | 小表 |
| `factor_metadata` | **Hot (NVMe)** | < 0.1 GB | 因子描述/参数，小表 |
| `regime_transition_log` | **Hot (NVMe)** | < 0.5 GB | 事件驱动，小表 |
| `strategy_run_summary` | **Hot (NVMe)** | ~0.5 GB | 查询列表频繁 |
| `kg.documents` | **Hot (NVMe)** | ~0.5 GB | 小表 |
| `kg.events` | **Hot (NVMe)** | ~1 GB | 高频查询 |
| `kg.graph_ingestions` | **Hot (NVMe)** | < 0.1 GB | 小表 |
| `kg.daily_runs` | **Hot (NVMe)** | < 0.1 GB | 小表 |
| `kg.embeddings` (PGVector) | **Hot (NVMe)** | ~11-42 GB | **KNN 搜索是随机读密集型，必须 NVMe** |
| PostgreSQL WAL + 系统开销 | **Hot (NVMe)** | ~15 GB | 系统必需 |
| **NVMe 小计** | | **~30-60 GB** | **仅占 2TB 的 1.5-3%** |

### 3.2 放 SATA SSD（温存储）— 所有业务数据主体

| 表名模式 | 示例 | 存储层 | 估算大小 (10年) | 理由 |
|---------|------|--------|----------------|------|
| `bars_*_daily_*` | `bars_stock_zh_a_daily_nf` | **Warm (SATA)** | ~42 GB | 大且持续增长，SATA 足够 |
| `bars_*_1min_*` | `bars_stock_zh_a_1min_nf` | **Warm (SATA)** | ~100-130 GB 压缩后 | 最大单项数据 |
| `bars_*_5min_*` / `*_15min_*` | — | **Warm (SATA)** | ~15-35 GB | 同上 |
| `bars_ext_*` | `bars_ext_baostock_*` | **Warm (SATA)** | ~20 GB | 扩展指标 |
| `industry_constituent` | — | **Warm (SATA)** | ~0.5 GB | 与行业权重一起 |
| `industry_weight` | — | **Warm (SATA)** | ~50 GB | 日度权重，大表 |
| `industry_daily` | — | **Warm (SATA)** | ~0.5 GB | 与行业数据一起 |
| `financial_statement` | — | **Warm (SATA)** | ~7.5 GB | JSONB 大表 |
| `corporate_action` | — | **Warm (SATA)** | ~0.5 GB | 与财务一起 |
| `factor_daily` | — | **Warm (SATA)** | **~50-300 GB** | **最大增长项** |
| `factor_correlation` | — | **Warm (SATA)** | ~5-20 GB | 因子相关性 |
| `regime_state` | — | **Warm (SATA)** | ~1-5 GB | 与因子同域 |
| `regime_indicator` | — | **Warm (SATA)** | ~5-10 GB | 同上 |
| `strategy_run_artifact` | — | **Warm (SATA)** | ~50-500 GB | 回测制品，不可预测 |
| `kg.extractions` | — | **Warm (SATA)** | ~10-50 GB | JSONB 大表 |
| `kg.impact_logs` | — | **Warm (SATA)** | ~5-20 GB | 持续增长 |
| 未来新增数据源 | 债券/期权/宏观/另类数据 | **Warm (SATA)** | ~100-500 GB | **必须预留** |
| **SATA 小计** | | | **~350-1700 GB** | **8TB 足够 5-10 年** |

### 3.3 与前版对比

| 数据 | v1 分配 | v2 分配 | 变更原因 |
|------|--------|---------|---------|
| 日线行情 | NVMe | **→ SATA** | 42 GB 且持续增长，避免未来搬迁 |
| 扩展指标 | NVMe | **→ SATA** | 同上 |
| 行业权重 | NVMe | **→ SATA** | 50 GB，大且增长中 |
| 财务数据 | NVMe | **→ SATA** | 7.5 GB，不够小 |
| 策略回测近期 | NVMe | **→ SATA** | 避免归档搬迁复杂度 |
| 因子数据近3年 | NVMe | **→ SATA** | 372+ 因子远超原估，直接放大盘 |
| KG extractions | NVMe | **→ SATA** | 10-50 GB，持续增长 |
| KG embeddings | NVMe | NVMe ✅ | KNN 必须低延迟，保持不变 |
| 元数据小表 | NVMe | NVMe ✅ | < 1 GB，保持不变 |

---

## 四、TimescaleDB 配置

### 4.1 Hypertable 规划（全部在 warm_storage 表空间）

| 表 | 分区键 | Chunk 间隔 | 压缩 | 表空间 |
|----|--------|-----------|------|--------|
| `bars_*_daily_*` | `trade_date` | 1 year | ✅ segmentby=symbol | warm_storage |
| `bars_*_1min_*` | `trade_date` | 1 week | ✅ segmentby=symbol | warm_storage |
| `bars_*_5min_*` | `trade_date` | 2 weeks | ✅ segmentby=symbol | warm_storage |
| `factor_daily` | `trade_date` | 3 months | ✅ segmentby=factor_id,symbol | warm_storage |
| `regime_state` | `trade_date` | 1 year | ✅ segmentby=market | warm_storage |
| `industry_weight` | `trade_date` | 1 year | ✅ segmentby=index_code | warm_storage |
| `industry_daily` | `trade_date` | 1 year | ✅ segmentby=index_code | warm_storage |

```sql
-- 示例：因子表建在 warm_storage 上
CREATE TABLE factor_daily (
    trade_date    DATE         NOT NULL,
    symbol        VARCHAR(32)  NOT NULL,
    factor_id     VARCHAR(64)  NOT NULL,
    factor_value  DOUBLE PRECISION,
    z_score       DOUBLE PRECISION,
    percentile    DOUBLE PRECISION,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
) TABLESPACE warm_storage;

SELECT create_hypertable('factor_daily', 'trade_date',
    chunk_time_interval => INTERVAL '3 months'
);

ALTER TABLE factor_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'factor_id,symbol',
    timescaledb.compress_orderby = 'trade_date DESC'
);
SELECT add_compression_policy('factor_daily', INTERVAL '6 months');

-- 因子元数据 — 小表，放 NVMe（默认表空间）
CREATE TABLE factor_metadata (
    factor_id     VARCHAR(64) PRIMARY KEY,
    factor_name   VARCHAR(128) NOT NULL,
    category      VARCHAR(32)  NOT NULL,
    subcategory   VARCHAR(64),
    description   TEXT,
    formula       TEXT,
    data_source   VARCHAR(64),
    frequency     VARCHAR(16) DEFAULT 'daily',
    universe      VARCHAR(32) DEFAULT 'zh_a',
    params        JSONB DEFAULT '{}',
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 日线行情也直接建在 warm_storage
CREATE TABLE bars_stock_zh_a_daily_nf (...) TABLESPACE warm_storage;
```

### 4.2 不使用 Hypertable 的表

| 表 | 理由 |
|----|------|
| `security_registry` | 非时序，小表 |
| `taxonomy_category` / `taxonomy_security_map` | 非时序，小表 |
| `financial_statement` / `corporate_action` | 按 reporting_period 非均匀时序 |
| `strategy_run_summary` / `strategy_run_artifact` | 按 run_id 查询 |
| `kg.*` 所有表 | 事件驱动，非均匀时序 |
| `factor_metadata` | 元数据，非时序 |

---

## 五、存储分层总览

```
2TB M.2 NVMe (pg_default) — 目标: 仅 ~30-60 GB
├── KG embeddings (PGVector HNSW)              ~11-42 GB   ← KNN 必须 NVMe
├── 元数据小表 (security_registry, taxonomy_*,
│   factor_metadata, kg.documents/events 等)   < 5 GB
├── strategy_run_summary                        ~0.5 GB
├── PostgreSQL WAL + 系统开销                    ~15 GB
└── MySQL 过渡期 (迁移完删)                     ~50 GB
    NVMe 总计: ~80 GB → 仅用 4% → 极其宽裕

8TB SATA SSD (warm_storage) — 目标: ~350-1700 GB
├── PostgreSQL warm_storage 表空间
│   ├── 行情数据 (日线+分钟线+扩展)             ~200-230 GB
│   ├── 行业数据 (权重+成分+日行情)             ~51 GB
│   ├── 财务数据 (报表+公司行为)                ~8 GB
│   ├── 因子数据 (全量，372+ 因子)              ~50-300 GB   ← 最大增长项
│   ├── Regime 数据                             ~6-15 GB
│   ├── 策略回测制品 (全量)                     ~50-500 GB
│   ├── KG 抽取/影响日志                        ~15-70 GB
│   └── 未来新增数据源预留                       ~100-500 GB
├── 备份区 (/sata8t/backups)                    ~300-900 GB
├── 数据湖 (/sata8t/data_lake)                  ~500 GB-2 TB
└── 临时计算空间 (/sata8t/scratch)              ~200 GB
    SATA 总计: ~1.5-4 TB → 50% 容量 → 安全余量充足
```

---

## 六、数据生命周期管理

### 6.1 简化策略（无搬迁）

| 数据 | 策略 | 说明 |
|------|------|------|
| 所有业务数据 | **建表时直接指定 `TABLESPACE warm_storage`** | 一次到位，不做后续搬迁 |
| TimescaleDB 压缩 | 超过 6 个月自动压缩 | 节省空间，不影响查询 |
| 数据保留 | **不删除**（数据是资产） | 8TB 足够 10 年 |

### 6.2 压缩策略

| 数据类型 | 压缩延迟 | 预期压缩比 |
|---------|---------|-----------|
| 分钟线行情 | 3 months | 10-15x |
| 日线行情 | 6 months | 8-12x |
| 因子数据 | 6 months | 10-20x |
| 行业权重 | 6 months | 8-12x |

---

## 七、监控与容量预警

```sql
-- 各表空间使用量
SELECT spcname,
       pg_size_pretty(pg_tablespace_size(oid)) AS size
FROM pg_tablespace;

-- 各表大小 TOP 20
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
       COALESCE(t.tablespace, 'pg_default') AS tablespace
FROM pg_tables t
WHERE schemaname IN ('public', 'kg')
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
LIMIT 20;
```

### 容量预警阈值

| 存储 | 容量 | 黄色预警 | 红色预警 |
|------|------|---------|---------|
| NVMe | 2 TB | 10% (200 GB) | 25% (500 GB) |
| SATA SSD | 8 TB | 60% (4.8 TB) | 80% (6.4 TB) |

> NVMe 阈值很低是因为我们现在只放 <100 GB 数据在上面，如果用量异常增长说明有数据被误放。

---

## 八、决策变更日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-05-09 | 初始版本 (v1) | 基于 INFRASTRUCTURE_AND_DATA_ENGINE.md §4 细化 |
| 2026-05-09 | **v2 大改** | 1) 因子数据量按 372+ 因子重新估算，远超 v1 的 100 因子假设;<br>2) SATA SSD 550MB/s 对个人使用足够快，不需要追求 NVMe;<br>3) 避免数据搬迁策略：大数据量直接放 8TB SATA;<br>4) NVMe 仅保留 PGVector KNN + 元数据小表 + 系统开销 |
