# Chaos 平台 — 基础设施与数据引擎规划

> 本文档记录 Chaos 平台级的基础设施决策，包括硬件资源分配、虚拟机规划、数据库引擎选型、存储分层策略和备份方案。
>
> 这些决策影响所有服务（phoenixA / artemis / atlas / cronjob / cthulhu），不属于任何单一项目。

---

## 一、硬件资产清单

**服务器**：Dell R730，双路 Xeon E5-2683 v4 × 2（共 32 核 64 线程），128 GB RAM

| # | 设备 | 类型 | 容量 | 速度 | 当前用途 |
|---|------|------|------|------|---------|
| A | M.2 NVMe | SSD | 512 GB | ~3500 MB/s | Docker 服务 VM（32 GB RAM）+ 开发机 VM（16 GB RAM） |
| B | M.2 NVMe | SSD | 2 TB | ~3500 MB/s | MySQL + Redis（Redis 已停用）VM（32-48 GB RAM） |
| C | 长城 SATA | SSD | 8 TB | ~550 MB/s | **空闲** |
| D | 挂载到 Docker VM | — | 2.7 TB | — | MinIO 对象存储 |

**内存分配现状**：

| 虚拟机 | 内存 | 存储 | 用途 |
|--------|------|------|------|
| Docker 服务 VM | 32 GB | 512 GB NVMe + 2.7 TB(MinIO) | phoenixA, artemis, cronjob, cthulhu, MinIO 等 Docker 容器 |
| 开发机 VM | 16 GB | 512 GB NVMe 剩余(~64 GB) | 开发环境 |
| 数据库 VM | 32-48 GB | 2 TB NVMe | MySQL (+ Redis 已停用) |
| **未分配** | ~32-48 GB | 8 TB SATA SSD | — |

---

## 二、虚拟机规划（目标状态）

### 2.1 方案：3 个虚拟机（保持现有 VM 结构，调整职责）

> 不新建 VM，在现有 3 个 VM 基础上调整分工。

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Dell R730  (128 GB RAM, 32C/64T)                         │
│                                                                                 │
│  ┌─────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │  VM1: Docker 服务 VM         │  │  VM2: 数据库 VM                          │  │
│  │  RAM: 48 GB (↑从32GB升)      │  │  RAM: 48 GB                              │  │
│  │  存储: 512GB NVMe            │  │  存储: 2TB NVMe (热) + 8TB SATA (温/冷)  │  │
│  │        + 2.7TB MinIO 挂载    │  │                                          │  │
│  │                              │  │  ┌────────────────────────────────┐      │  │
│  │  Docker Compose:             │  │  │ PostgreSQL 16                  │      │  │
│  │  ├── phoenixa  (Go)          │  │  │ + TimescaleDB + PGVector       │      │  │
│  │  ├── atlas     (Python)      │  │  │ 数据目录: 2TB NVMe             │      │  │
│  │  ├── artemis   (Python)      │  │  │ cold_storage: 8TB SATA SSD    │      │  │
│  │  ├── cronjob   (Go)          │  │  │                                │      │  │
│  │  ├── cthulhu   (nginx)       │  │  │ database: chaos_db             │      │  │
│  │  ├── neo4j     (图谱)        │  │  │ ├── schema: public (phoenixA) │      │  │
│  │  └── minio     (2.7TB)       │  │  │ └── schema: kg (atlas)        │      │  │
│  │                              │  │  └────────────────────────────────┘      │  │
│  │  Neo4j 数据: 512GB NVMe      │  │                                          │  │
│  └─────────────────────────────┘  │  备份目标: 8TB SATA SSD                   │  │
│                                    └──────────────────────────────────────────┘  │
│  ┌─────────────────────────────┐                                                │
│  │  VM3: 开发机                 │                                                │
│  │  RAM: 16 GB                  │                                                │
│  │  存储: 512GB NVMe 剩余       │                                                │
│  └─────────────────────────────┘                                                │
│                                                                                 │
│  未分配 RAM: ~16 GB → 留作 Kafka/Flink 预留 或 VM1/VM2 扩容缓冲                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 内存分配（目标状态）

| 虚拟机 | 内存 | 说明 |
|--------|------|------|
| VM1 Docker 服务 | **48 GB** | 从 32→48，承载 Neo4j + atlas + artemis 等 |
| VM2 数据库 | **48 GB** | 维持不变，MySQL 迁移后腾出给 PostgreSQL |
| VM3 开发机 | **16 GB** | 不变 |
| **预留** | **16 GB** | Kafka/Flink、或紧急扩容 |
| **总计** | **128 GB** | |

### 2.3 VM1 Docker 服务 — 内存细分

| 组件 | 内存 | 说明 |
|------|------|------|
| Neo4j | 6-8 GB | heap=3GB + pagecache=3-5GB（图遍历需要） |
| atlas | 2-3 GB | FastAPI + PDF解析 + LLM 调用峰值 |
| artemis | 2-3 GB | 量化回测计算峰值 |
| phoenixA | 0.5 GB | Go 服务，内存占用小 |
| cronjob | 0.2 GB | Go 服务 |
| cthulhu (nginx) | 0.1 GB | 静态文件服务 |
| MinIO | 2 GB | 对象存储 |
| **OS + 文件系统缓存** | ~28 GB | Linux 页缓存（对 Neo4j pagecache 有帮助） |
| **总计** | ~48 GB | |

### 2.4 VM2 数据库 — 内存细分

| 组件 | 内存 | 说明 |
|------|------|------|
| PostgreSQL shared_buffers | 12 GB | 48 GB RAM 的 25%，标准推荐 |
| PostgreSQL effective_cache_size | 36 GB | 告诉查询优化器可用内存 |
| PostgreSQL work_mem | 256 MB | 复杂查询排序/哈希用 |
| PostgreSQL maintenance_work_mem | 1 GB | VACUUM / CREATE INDEX 用 |
| MySQL（迁移过渡期） | 8-16 GB | 迁移完成后释放 |
| **OS + 文件系统缓存** | 剩余 | PostgreSQL 依赖 OS 缓存读热数据 |
| **总计** | 48 GB | |

### 2.5 为什么 DB 和 App 分开两个 VM？

| 考虑 | 分析 |
|------|------|
| **已有 VM 结构** | 数据库 VM 已存在且配好了 2TB NVMe，不需要重建 |
| **IO 隔离** | PostgreSQL 密集刷盘（WAL/checkpoint）不会影响应用服务响应 |
| **内存隔离** | PostgreSQL shared_buffers 需要稳定大内存，不被应用 OOM 抢占 |
| **备份隔离** | DB VM 独立做 pg_basebackup，不影响服务可用性 |
| **网络延迟** | 同一物理机内 VM 间通信 < 0.1ms，可忽略 |

### 2.6 Neo4j 为什么放 VM1（服务 VM）不放 VM2（数据库 VM）？

| 考虑 | 分析 |
|------|------|
| **atlas 专属** | Neo4j 只有 atlas 使用，和 atlas 放一起部署最简单 |
| **数据量小** | 图谱节点/边预计 < 100 万，数据 < 5 GB，不需要 2TB 大盘 |
| **直连最快** | atlas 和 Neo4j 在同一个 Docker Compose 网络里，Bolt 协议零延迟 |
| **不影响 PG** | Neo4j 的随机读 IO 模式和 PostgreSQL 的顺序扫描不同，放一起会互相干扰 |

### 2.7 Kafka + Flink 预留

当前 16GB 未分配内存可用于后续流处理需求：

| 组件 | 最小内存 | 说明 |
|------|---------|------|
| Kafka (KRaft 模式) | 4-6 GB | 不需要 ZooKeeper，单节点够用 |
| Flink (单机) | 6-8 GB | TaskManager 1-2 个 slot |
| **总计** | 10-14 GB | 在预留 16 GB 内 |

> 建议放 VM1（Docker 服务 VM），用 Docker Compose 统一管理。
> 触发条件：当需要实时事件流处理（如实时新闻 → 实时影响分析）时再引入。

---

## 三、数据引擎选型

### 3.1 统一方案：PostgreSQL 16 + 扩展

**结论：一个 PostgreSQL 实例，一个数据库（chaos_db），用 schema 隔离业务域。**

```
PostgreSQL 16 实例 (VM2, 2TB NVMe)
└── database: chaos_db
    ├── schema: public     ← phoenixA 现有表 (bars_*, security_*, taxonomy_*)
    └── schema: kg         ← atlas 知识图谱表 (documents, extractions, impact_logs)

扩展：
├── TimescaleDB  → K 线时序数据（日线/分钟级）
├── PGVector     → 文档/公司名 embedding 语义搜索
└── (标准 SQL)   → 结构化元数据、JSONB 查询
```

**为什么一个实例而非两个？**

- 1 份 shared_buffers（12GB），不浪费内存
- 1 次 pg_basebackup 覆盖全部数据
- phoenixA 可以跨 schema JOIN（如 `public.security_registry` ↔ `kg.documents`）
- 1 套连接池、1 套监控

### 3.2 MySQL → PostgreSQL 迁移

**结论：建议迁移，分阶段。**

#### 价值评估

| 能力 | MySQL 现状 | PostgreSQL 优势 | 价值 |
|------|-----------|----------------|------|
| **JSONB** | JSON 类型有，查询效率一般 | 原生 JSONB + GIN 索引 | ⭐⭐⭐ atlas 刚需 |
| **时序数据** | 无原生支持，靠分区表 | TimescaleDB：自动分区、压缩（10-20x）、连续聚合 | ⭐⭐⭐ K 线质变 |
| **向量检索** | 不支持 | PGVector：余弦/欧氏/内积相似度 | ⭐⭐ 后续语义搜索 |
| **分区策略** | 手动 RANGE 分区 | 声明式分区 + TimescaleDB 自动 chunk | ⭐⭐ 运维省心 |
| **MVCC** | gap lock 问题多 | 真正的 MVCC，并发读写更好 | ⭐ |

#### 迁移成本

| 工作项 | 预估工时 | 说明 |
|--------|---------|------|
| phoenixA Go 驱动切换 | 1-2 天 | `go-sql-driver/mysql` → `pgx`，GORM 换 `gorm.io/driver/postgres` |
| DDL 转换 | 1 天 | `AUTO_INCREMENT` → `SERIAL`，`DATETIME` → `TIMESTAMP` |
| 数据迁移脚本 | 1 天 | `pgloader` 自动转换 |
| SQL 语法差异 | 0.5 天 | 反引号 → 双引号，`IFNULL` → `COALESCE` |
| 框架 infra 层改动 | 1-2 天 | `components/mysql` → `components/postgres` |
| **总计** | **~5-7 天** | 一次性投入 |

#### 迁移策略

```
Phase A（现在）：
  - VM2 上安装 PostgreSQL（与 MySQL 共存，2TB NVMe 足够）
  - atlas 的 kg.* 表先建在 PostgreSQL 里
  - phoenixA 新增 pg 数据源，对 atlas 暴露 kg.* 的 CRUD API

Phase B（后续）：
  - pgloader 迁移 MySQL 数据 → PostgreSQL (public schema)
  - phoenixA GORM 切换到 postgres driver
  - 验证通过后停掉 MySQL
  - K 线表转 TimescaleDB hypertable
```

### 3.3 PGVector vs Qdrant

**结论：PGVector，不引入 Qdrant。**

| 对比项 | PGVector | Qdrant |
|--------|----------|--------|
| 部署 | `CREATE EXTENSION vector`（零成本） | 单独 Docker 容器 |
| 运维 | 跟 PostgreSQL 一起备份/监控 | 独立运维 |
| 性能 | < 500 万向量够用 | 千万级以上有优势 |
| 当前需求 | atlas 文档/公司名 embedding（< 10 万条） | — |

→ 10 万条向量用 Qdrant 是杀鸡用牛刀。

### 3.4 TimescaleDB vs ClickHouse

**结论：TimescaleDB（PostgreSQL 扩展），不引入 ClickHouse。**

| 对比项 | TimescaleDB | ClickHouse |
|--------|-------------|------------|
| 架构 | PG 扩展，同实例 | 独立服务 |
| 写入 | 行级 INSERT/UPSERT | 批量 INSERT，不擅长 UPSERT |
| 压缩 | 10-20x | 更强（列式 + LZ4） |
| 实时写入 | ✅ 原生支持 | 需要 buffer 或 Kafka 中转 |
| 运维 | 低（就是 PostgreSQL） | 高（独立集群） |
| 适用数据量 | 十亿行级够用 | 百亿行级才体现优势 |

**分钟级数据量估算**：
```
A 股 ~5000 只 × 240 分钟/天 × 250 交易日/年
= 3 亿行/年（1min 频率）
= 6000 万行/年（5min 频率）
```

→ TimescaleDB 压缩后完全够用。ClickHouse 运维代价远大于收益。

### 3.5 数据引擎统一全景

```
┌──────────────────────────────────────────────────────────────────┐
│            PostgreSQL 16 (1 个实例, VM2, 2TB NVMe)               │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐               │
│  │  标准 SQL     │ │ TimescaleDB  │ │ PGVector   │               │
│  │              │ │ (时序扩展)    │ │ (向量扩展)  │               │
│  ├──────────────┤ ├──────────────┤ ├────────────┤               │
│  │ kg.documents │ │ bars_*       │ │ embeddings │               │
│  │ kg.extract.. │ │ (日线/分钟)  │ │ (文档/公司) │               │
│  │ kg.impact_.. │ │ 自动分区     │ │ KNN 搜索   │               │
│  │ security_reg │ │ 压缩 10-20x  │ │            │               │
│  │ taxonomy_*   │ │ 连续聚合     │ │            │               │
│  └──────────────┘ └──────────────┘ └────────────┘               │
│                                                                  │
│  → 一套备份、一套监控、一套连接池、一套运维                       │
│  → 个人开发者的最优解                                             │
└──────────────────────────────────────────────────────────────────┘

何时需要 ClickHouse/Qdrant？
  - 数据量 > 50 亿行 (ClickHouse)
  - 向量 > 1000 万条 (Qdrant)
  → 按当前规模，3-5 年内不需要。
```

---

## 四、数据量估算与存储分层策略

### 4.1 完整数据量估算

> 基于 phoenixA 现有表结构 + 未来扩展需求（港股/美股/ETF/期货/现货/分钟线/因子），逐项估算。

#### 4.1.1 日线行情（bars_*_daily_*）

| 市场 | 标的数 | 历史年数 | 复权类型 | 行数 | 每行 ~100B | 含索引 |
|------|--------|---------|---------|------|-----------|--------|
| A 股 | 5,000 | 20 年 | nf + hfq + qfq (3种) | 75M | 7.5 GB | ~12 GB |
| 港股 | 2,500 | 25 年 | nf + hfq (2种) | 31M | 3.1 GB | ~5 GB |
| 美股 | 8,000 | 30 年 | nf + adj (2种) | 120M | 12 GB | ~20 GB |
| Index | 800 | 20 年 | nf | 4M | 0.4 GB | ~0.7 GB |
| ETF | 4,000 | 10 年 | nf + hfq (2种) | 20M | 2 GB | ~3.5 GB |
| 期货 | 500 | 15 年 | nf | 1.9M | 0.2 GB | ~0.3 GB |
| 现货/商品 | 100 | 20 年 | nf | 0.5M | ~0 | ~0.1 GB |
| **日线小计** | | | | **~252M** | | **~42 GB** |

#### 4.1.2 扩展指标（bars_ext_*）

| 数据 | 说明 | 估算 |
|------|------|------|
| PE/PB/换手率等 (类似 baostock) | A 股全市场 | ~12 GB |
| 美股基础指标 | 如有 | ~8 GB |
| **扩展小计** | | **~20 GB** |

#### 4.1.3 行业/分类数据

| 表 | 说明 | 估算 |
|----|------|------|
| taxonomy_category | 分类节点（万级） | < 0.1 GB |
| taxonomy_security_map | 证券-分类映射（十万级） | < 0.1 GB |
| industry_constituent | 行业成分股（百万级） | ~0.5 GB |
| industry_weight | **日度权重**（500行业 × 50成分 × 250天 × 10年 = 625M） | **~50 GB** |
| industry_daily | 行业日行情（500 × 250 × 10年 = 1.25M） | ~0.5 GB |
| **分类小计** | | **~51 GB** |

#### 4.1.4 财务/公司行为数据

| 表 | 说明 | 估算 |
|----|------|------|
| financial_statement | 三表 × 季度 × 15500 公司 × 20 年 ≈ 3.7M 行 × ~2KB JSON | ~7.5 GB |
| corporate_action | 分红/配股等 × 15500 × 20 年 × ~5 事件 ≈ 1.5M 行 | ~0.5 GB |
| **财务小计** | | **~8 GB** |

#### 4.1.5 策略回测数据

| 表 | 说明 | 估算 |
|----|------|------|
| strategy_run_summary | 回测汇总（万-十万级） | ~0.5 GB |
| strategy_run_artifact | **回测制品（LONGTEXT JSON，可能很大）** | **10-100 GB** |
| **策略小计** | | **~10-100 GB** |

> ⚠️ strategy_run_artifact 是最不可预测的。一次 campaign 扫描 5000 只股票 × 多参数组合，
> 每个制品几十 KB-几 MB，跑 100 次 campaign 就是 10-50 GB。

#### 4.1.6 分钟线行情（未来新增，最大项）

| 市场 | 标的数 | 每日分钟数 | 行/年 | 原始/年 | **TimescaleDB 压缩后/年** |
|------|--------|----------|-------|---------|------------------------|
| A 股 1min | 5,000 | 240 | 300M | 30 GB | **2-3 GB** |
| 港股 1min | 2,500 | 330 | 206M | 20 GB | **1.5 GB** |
| 美股 1min | 8,000 | 390 | 780M | 78 GB | **5-8 GB** |
| **分钟线/年** | | | **1.3B** | **128 GB** | **~9-13 GB** |
| 5 年累计 | | | 6.5B | 640 GB | **~50-65 GB** |
| 10 年累计 | | | 13B | 1.28 TB | **~100-130 GB** |

> **决策：分钟线全量直接放 8TB SATA SSD，不做 NVMe ↔ SATA 冷热迁移。**
>
> 理由：
> - 分钟线查询模式是按 symbol + 时间范围的**顺序读**，SATA SSD 550MB/s 足够
> - 单股查询（回测最常见场景）：1 年 = 6 万行 ≈ 几 MB → SATA SSD < 10ms 返回
> - 全市场扫描：压缩后几 GB → 顺序读 ~10 秒（回测是离线批处理，可接受）
> - 简化运维：**省掉 TimescaleDB tiered_storage_policy 的配置和维护**
> - NVMe 空间全部留给高频随机读的数据（日线回测、JSONB 查询、图谱）
>
> 做法：分钟线 hypertable 整体建在 8TB SATA SSD 的表空间上
> ```sql
> -- 分钟线直接建在 SATA SSD 上
> CREATE TABLE bars_stock_zh_a_1min_nf (...) TABLESPACE warm_storage;
> SELECT create_hypertable('bars_stock_zh_a_1min_nf', 'trade_date',
>   chunk_time_interval => INTERVAL '1 week'
> );
> -- 压缩策略照常
> ALTER TABLE bars_stock_zh_a_1min_nf SET (
>   timescaledb.compress,
>   timescaledb.compress_segmentby = 'symbol',
>   timescaledb.compress_orderby = 'trade_date DESC'
> );
> SELECT add_compression_policy('bars_stock_zh_a_1min_nf', INTERVAL '3 months');
> ```

#### 4.1.7 Atlas 知识图谱数据（全球产业链视角）

> ⚠️ 虽然投资核心针对 A 股，但产业链是全球的。
>
> 示例：某 A 股公司依赖英伟达 GPU → NVIDIA 涨价 → 成本↑ → 利润↓
> 示例：中美贸易战 → 关税政策 → 影响所有出口导向公司
>
> 因此图谱必须覆盖全球关键公司/资源/政策，不能只有 A 股。

**Neo4j 图谱规模估算（全球产业链）**：

| 节点类型 | 仅 A 股 | **全球产业链** | 说明 |
|---------|---------|--------------|------|
| Company | 5,000 | **20,000-50,000** | A股5K + 港股2.5K + 美股核心3K + 全球供应链关键企业5-10K + 子公司 |
| Product | 10,000 | **50,000-100,000** | 每公司 2-5 个核心产品 |
| Resource | 200 | **500-1,000** | 全球大宗商品/能源/矿产/算力 |
| Technology | 1,000 | **5,000-10,000** | 半导体/AI/新能源/生物医药等全球技术 |
| Industry | 500 | **2,000-5,000** | 各国行业分类 |
| Event | 5,000/年 | **20,000-50,000/年** | 全球新闻/政策/财报（每日 50-200 条） |
| Policy | 500/年 | **2,000-5,000/年** | 各国监管/关税/贸易政策 |
| Asset/Market | 2,000 | **5,000-10,000** | |
| **总节点** | **~25K** | **~100K-230K** | |
| **总边（5-10x 节点）** | ~125K | **~500K-2.3M** | |

**Neo4j 存储估算**：

| 规模 | 节点 | 边 | 数据量 | 内存需求 |
|------|------|-----|--------|---------|
| 仅 A 股（初期） | 25K | 125K | < 1 GB | 3-4 GB |
| **全球产业链（目标）** | **100-230K** | **500K-2.3M** | **5-15 GB** | **6-10 GB** |
| 极端（5年后全量） | 500K | 5M | ~30 GB | 12-16 GB |

→ **当前 VM1 分配给 Neo4j 的 6-8 GB 足够覆盖全球产业链规模**。
→ 如果 5 年后增长到 500K 节点，可从 VM1 预留的 OS 缓存中再拨 4-8 GB。
→ 512 GB NVMe 上 Neo4j 数据 30 GB 也完全没问题。

**PGVector 向量规模估算（全球文档 + 实体）**：

| 向量来源 | 仅 A 股 | **全球产业链** | 维度 |
|---------|---------|--------------|------|
| 文档 chunk embedding | 50K | **200K-500K** | 1536 |
| 公司名 embedding | 5K | **50K** | 1536 |
| 产品/技术名 embedding | 10K | **100K** | 1536 |
| 事件描述 embedding | 10K/年 | **50K-100K/年** | 1536 |
| **总向量（3年累计）** | **~100K** | **~500K-1M** | |

**PGVector 存储估算**：

| 规模 | 向量数 | 原始数据 | HNSW 索引 | 总计 |
|------|--------|---------|-----------|------|
| 仅 A 股 | 100K | ~0.6 GB | ~1.5 GB | **~2 GB** |
| **全球（3年）** | **500K-1M** | **3-6 GB** | **8-15 GB** | **~11-21 GB** |
| 极端（5年） | 2M | 12 GB | 30 GB | ~42 GB |

→ **PGVector 500 万以下不需要 Qdrant**，当前全球规模 1M 级向量在 PGVector 能力范围内。
→ 向量数据在 NVMe 上（KNN 搜索是随机读密集型），这部分必须在 NVMe。
→ 2TB NVMe 上即使 42 GB 向量数据也完全可以容纳。

**PostgreSQL 表估算更新**：

| 表 | 说明 | 估算 |
|----|------|------|
| kg.documents | 文档元数据（万-十万级） | ~0.5 GB |
| kg.extractions | **JSONB 抽取结果**（全球文档，每条 5-50 KB） | **10-50 GB** |
| kg.impact_logs | 影响日志 JSONB（每日 50-200 条 × 365 天 × 年数） | **5-20 GB** |
| kg.daily_runs | 运行记录 | < 0.1 GB |
| kg.embeddings | PGVector 向量 + HNSW 索引 | **11-42 GB** |
| **KG 小计** | | **~27-113 GB** |

#### 4.1.8 预计算因子数据（未来可能新增）

| 场景 | 估算 |
|------|------|
| 日频因子：5000 股 × 100 因子 × 250 天 × 10 年 = 12.5 亿行 | 压缩后 ~30-80 GB |
| 分钟频因子：极大，一般不预存 | — |
| **因子小计** | **~30-80 GB（若预存）** |

#### 4.1.9 系统开销

| 项 | 估算 |
|----|------|
| PostgreSQL WAL | 2-10 GB |
| 索引开销（含 GIN、BRIN） | 表数据的 ~30-50% |
| pg_stat / 系统表 | ~1 GB |
| **系统小计** | ~10-20 GB |

---

#### 📊 总量汇总

| 数据分类 | 2TB NVMe（热） | 8TB SATA SSD（温/冷） | 说明 |
|---------|---------------|---------------------|------|
| 日线行情（全量全历史） | **42 GB** | — | 随机读密集，全留 NVMe |
| 扩展指标 | **20 GB** | — | 同上 |
| 行业/分类 | **51 GB** | — | industry_weight 最大 |
| 财务/公司行为 | **8 GB** | — | 同上 |
| 策略回测 | **10 GB** | **~90 GB**（历史制品） | 近期留 NVMe，旧的迁温盘 |
| **分钟线（全量）** | **—** | **~50-130 GB**（5-10年） | **全部放 SATA SSD** |
| Atlas KG（JSONB + 向量） | **~50 GB** | — | JSONB 查询 + KNN 搜索需 NVMe |
| 预计算因子（若有） | **~30 GB**（常用） | **~50 GB**（历史） | 按需分层 |
| 系统开销 | **~15 GB** | — | |
| **小计** | **~226 GB** | **~190-370 GB** | |
| MySQL（过渡期） | **~50 GB** | — | 迁移完删除 |
| 备份 | — | **~300-900 GB** | 详见第五章 |
| **总计** | **~276 GB** | **~500-1270 GB** | |
| **2 年后预估** | **~400-500 GB** | **~800 GB-1.5 TB** | |
| **5 年后预估** | **~500-700 GB** | **~1.5-3 TB** | KG 向量增长是 NVMe 主要增量 |

### 4.2 结论：2TB NVMe 够不够？

**结论：够。分钟线全放 SATA 后，NVMe 压力更小了。**

```
当前热数据：~276 GB → 2TB 用了 14%     ✅ 很宽裕
2 年后：    ~400-500 GB → 用了 20-25%    ✅ 没问题
5 年后：    ~500-700 GB → 用了 25-35%    ✅ 还行

NVMe 上最大增长项：
  1. Atlas KG 向量 (PGVector HNSW 索引)：随时间增长，5年后 ~42GB
  2. 日线行情（加新市场/新复权类型）：增长慢
  3. 策略回测制品（大的迁温盘）：可控
```

**关键变化（vs 之前方案）**：
- ✅ 分钟线不再放 NVMe → 省掉 ~7GB 热 + 省掉冷热迁移运维
- ✅ KG 向量数据放 NVMe → KNN 搜索需要随机读低延迟
- ✅ 即使全球产业链规模（500K-1M 向量），NVMe 上增加 ~11-42 GB，完全可控

### 4.3 8TB SATA SSD 怎么用才不浪费？

**新方案**：8TB = 分钟线主存储 + 温存储 + 备份 + 数据湖

```
8TB 长城 SATA SSD (/sata8t)
│
├── /sata8t/pgdata_warm/              ← PostgreSQL warm_storage 表空间
│   ├── 分钟线全量（所有市场所有历史）  ~50-130 GB（5-10 年，压缩后）
│   ├── 策略回测历史制品                ~50-100 GB（按时间迁移）
│   ├── 预计算因子（历史/非高频访问）   ~50 GB
│   └── industry_weight 历史（若增长快）按需
│
├── /sata8t/backups/                  ← 备份区
│   ├── pg_basebackup/                ~200-800 GB（4 份全量）
│   ├── pg_wal_archive/               ~20-50 GB（7 天 WAL）
│   ├── neo4j_dump/                   ~7-30 GB（7 天 dump）
│   └── mysql_snapshot/               ~50 GB（迁移前保留）
│
├── /sata8t/data_lake/                ← 数据湖
│   ├── tick_data/                    未来 tick 级数据（Parquet/CSV）
│   ├── alternative_data/            另类数据（舆情/卫星/供应链等）
│   └── research_cache/              研报/财报原始文件备份（MinIO 副本）
│
└── /sata8t/scratch/                  ← 临时计算空间
    └── 大规模回测/因子挖掘的临时输出

空间规划：
  分钟线全量：~50-130 GB（增长中，最大单项）
  温存储：    ~100-150 GB（增长中）
  备份：      ~300-900 GB
  数据湖：    ~500 GB-2 TB（按需增长）
  临时：      ~200 GB
  总计：      ~1.2-3.4 TB（8TB 还有大量空间）
  预留：      ~4.6-6.8 TB（给 tick、另类数据、或扩展）
```

### 4.4 磁盘最终分配

```
VM2 数据库虚拟机
├── 2TB NVMe — 性能盘：热数据（当前 ~276GB，5 年后 ~700GB）
│   ├── PostgreSQL 主数据目录 (/nvme/pgdata)
│   │   ├── 全部日线行情（所有市场、所有复权，全历史 ~42GB）
│   │   ├── 扩展指标（~20GB）
│   │   ├── 行业/分类（~51GB）
│   │   ├── 财务/公司行为（~8GB）
│   │   ├── 策略回测（近期 ~10GB）
│   │   ├── Atlas KG JSONB + 向量（~50GB，含 HNSW 索引）
│   │   ├── 预计算因子（常用 ~30GB）
│   │   ├── security_registry / taxonomy
│   │   └── WAL 日志（~5GB）
│   └── MySQL（过渡期 ~50GB → 迁移完删除释放）
│   ※ 分钟线不在 NVMe 上
│
└── 8TB 长城 SATA SSD — 分钟线 + 温存储 + 备份 + 数据湖
    ├── PostgreSQL warm_storage 表空间
    │   ├── 分钟线全量（所有市场全历史 ~50-130GB 压缩后）
    │   ├── 策略回测历史制品（~50-100GB）
    │   └── 预计算因子历史（~50GB）
    ├── 备份区（~300-900GB）
    │   ├── pg_basebackup/（4 份全量）
    │   ├── pg_wal_archive/（7 天 WAL）
    │   ├── neo4j_dump/（7 天 dump）
    │   └── mysql_snapshot/（迁移前保留）
    ├── 数据湖（~500GB-2TB，按需增长）
    │   ├── tick_data/（未来）
    │   ├── alternative_data/（另类数据）
    │   └── research_cache/（研报备份）
    └── 临时计算空间（~200GB）

VM1 Docker 服务虚拟机
├── 512GB NVMe
│   ├── Docker 数据 (/var/lib/docker)
│   ├── Neo4j 数据 (~5-30GB，全球产业链图谱)
│   └── 应用日志
└── 2.7TB MinIO 挂载
    └── atlas-documents/ bucket (财报/研报/新闻)
```

### 4.5 PostgreSQL 如何用一个实例读写两块盘？— Tablespace（表空间）

> ❓ **核心问题**：PostgreSQL 数据目录在 2TB NVMe 上，怎么让部分表的数据存到 8TB SATA SSD 上？
>
> ✅ **答案**：PostgreSQL 原生的 **Tablespace** 功能，无需任何额外组件。

#### 什么是 Tablespace？

Tablespace 是 PostgreSQL 的「存储位置映射」机制：
- **默认表空间** `pg_default` → 指向 PostgreSQL 主数据目录（`/nvme/pgdata`，在 2TB NVMe 上）
- **自定义表空间** → 可以指向任意文件系统路径（比如 `/sata8t/pgdata_warm`，在 8TB SATA SSD 上）

```
PostgreSQL 实例（1 个进程，1 个端口 5432）
│
├── 默认表空间 pg_default → /nvme/pgdata/base/      ← 2TB NVMe
│   ├── 日线行情表
│   ├── Atlas KG 表（JSONB 查询密集）
│   ├── PGVector 向量表（KNN 随机读）
│   ├── 财务/分类表
│   └── WAL 日志
│
└── 自定义表空间 warm_storage → /sata8t/pgdata_warm/  ← 8TB SATA SSD
    ├── 分钟线行情表（全量，顺序读为主）
    ├── 策略回测历史制品
    └── 预计算因子历史
```

#### 底层原理

```
/nvme/pgdata/                          # PostgreSQL 主数据目录 (2TB NVMe)
├── base/                              # pg_default 表空间的实际数据
│   ├── 16384/                         # chaos_db 数据库 OID
│   │   ├── 12345                      # bars_stock_zh_a_daily_nf 表文件
│   │   ├── 12346                      # kg.documents 表文件
│   │   └── ...
├── pg_tblspc/                         # 表空间的符号链接目录
│   └── 24576 → /sata8t/pgdata_warm    # warm_storage 表空间 → 指向 SATA SSD
├── pg_wal/                            # WAL 日志（始终在主目录）
└── postgresql.conf

/sata8t/pgdata_warm/                   # warm_storage 表空间的实际数据 (8TB SATA SSD)
├── PG_16_202307071/                   # PostgreSQL 版本目录
│   └── 16384/                         # chaos_db 数据库 OID
│       ├── 56789                      # bars_stock_zh_a_1min_nf 表文件
│       ├── 56790                      # strategy_run_artifact_archive 表文件
│       └── ...
```

**关键点**：
- PostgreSQL 通过 `pg_tblspc/` 目录下的**符号链接**找到其他磁盘上的数据
- 所有表空间共享**同一个 shared_buffers**、同一个连接池、同一份 WAL
- 对应用完全透明——SQL 查询 `SELECT * FROM bars_stock_zh_a_1min_nf` 不需要知道数据在哪块盘
- `pg_basebackup` 会自动备份所有表空间（包括其他盘上的）

#### VM2 挂盘要求

```
VM2 数据库虚拟机
├── /nvme     ← 虚拟磁盘 1（透传或 virtio 映射 2TB NVMe）
│   └── /nvme/pgdata    ← PostgreSQL 数据目录（data_directory）
│
└── /sata8t   ← 虚拟磁盘 2（透传或 virtio 映射 8TB SATA SSD）
    ├── /sata8t/pgdata_warm   ← warm_storage 表空间目录（属主 postgres:postgres）
    └── /sata8t/backups       ← 备份目录
```

> ⚠️ **前提**：8TB SATA SSD 必须作为第二块虚拟磁盘挂载到 VM2 中。
> 在 hypervisor（Proxmox/ESXi/KVM）中给 VM2 添加一块 virtio 磁盘，指向 8TB SATA SSD 分区。
> 开机后在 VM2 内 `mount` 到 `/sata8t`，加入 `/etc/fstab` 保证开机自动挂载。

#### 完整操作步骤

```bash
# ── 在 VM2 上执行 ────────────────────────────

# 1. 确认 8TB SATA SSD 已挂载
lsblk                                  # 确认看到第二块磁盘，比如 /dev/vdb
mount | grep sata8t                    # 确认已挂载到 /sata8t

# 2. 创建表空间目录并设权限
sudo mkdir -p /sata8t/pgdata_warm
sudo chown postgres:postgres /sata8t/pgdata_warm
sudo chmod 700 /sata8t/pgdata_warm

# 3. 在 PostgreSQL 中创建表空间（以 superuser 身份）
sudo -u postgres psql -d chaos_db -c \
  "CREATE TABLESPACE warm_storage LOCATION '/sata8t/pgdata_warm';"

# 4. 验证
sudo -u postgres psql -d chaos_db -c \
  "SELECT spcname, pg_tablespace_location(oid) FROM pg_tablespace;"
# 应该看到：
#   spcname       | pg_tablespace_location
#  ---------------+------------------------
#   pg_default    |
#   pg_global     |
#   warm_storage  | /sata8t/pgdata_warm

# 5. 把分钟线表建在 warm_storage 上
# （见下方「表空间与压缩配置」）
```

#### 常用表空间管理命令

```sql
-- 查看所有表空间
SELECT spcname, pg_tablespace_location(oid),
       pg_size_pretty(pg_tablespace_size(oid)) as size
FROM pg_tablespace;

-- 查看某个表在哪个表空间
SELECT tablename, tablespace
FROM pg_tables WHERE schemaname = 'public';
-- tablespace 为 NULL 表示在默认表空间 (pg_default = NVMe)

-- 移动现有表到另一个表空间（在线操作，会短暂锁表）
ALTER TABLE bars_stock_zh_a_1min_nf SET TABLESPACE warm_storage;

-- 移动回默认表空间
ALTER TABLE bars_stock_zh_a_1min_nf SET TABLESPACE pg_default;

-- 移动整个 schema 的所有表（批量）
-- 需要逐表执行，或用脚本：
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'bars_%_1min_%'
  LOOP
    EXECUTE format('ALTER TABLE %I SET TABLESPACE warm_storage', r.tablename);
  END LOOP;
END $$;
```

### 4.6 表空间与压缩配置

```sql
-- ① 在 8TB SATA SSD 上创建温存储表空间（4.5 节已执行）
CREATE TABLESPACE warm_storage LOCATION '/sata8t/pgdata_warm';

-- ② 分钟线直接建在 SATA SSD 上（不做冷热迁移）
CREATE TABLE bars_stock_zh_a_1min_nf (...) TABLESPACE warm_storage;
CREATE TABLE bars_stock_hk_1min_nf (...) TABLESPACE warm_storage;
CREATE TABLE bars_stock_us_1min_nf (...) TABLESPACE warm_storage;

-- ③ 转为 TimescaleDB hypertable + 压缩
SELECT create_hypertable('bars_stock_zh_a_1min_nf', 'trade_date',
  chunk_time_interval => INTERVAL '1 week'
);
ALTER TABLE bars_stock_zh_a_1min_nf SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'symbol',
  timescaledb.compress_orderby = 'trade_date DESC'
);
SELECT add_compression_policy('bars_stock_zh_a_1min_nf', INTERVAL '3 months');
-- 港股、美股同样操作

-- ④ 日线：留 NVMe 默认表空间，不分层（全量 ~42GB）

-- ⑤ 策略制品历史迁移（非 hypertable，用定时脚本）
-- 每月将 6 个月前的 strategy_run_artifact 移到温盘分区表
```

> 对比原方案去掉了 `cold_storage` 表空间 和 `add_tiered_storage_policy`，
> 简化为：分钟线 **一开始就在 SATA SSD 上**，无需运维迁移策略。

### 4.7 回测场景对冷热分层的影响

**结论：不影响。**

```
1. PostgreSQL tablespace 对查询完全透明，一条 SQL 自动合并冷热数据：
   SELECT * FROM bars_stock_zh_a_1min_nf
   WHERE symbol='600519' AND trade_date BETWEEN '2025-01-01' AND '2026-04-29';
   -- 近期从 NVMe 读，历史从 SATA 读，结果自动 UNION

2. 日线回测（最常见）：
   全量在 NVMe 上（全市场全历史 ~42GB），零影响

3. 分钟线回测：
   单股 1 年 = 6 万行 ≈ 几 MB → SATA SSD (550MB/s) 瞬间返回
   全市场 1 年 = 3 亿行 → 压缩后几 GB → SATA SSD 顺序读 ~10 秒
   → 完全可接受（回测本身是离线批处理）

4. 真正的瓶颈在 CPU（因子计算/信号/交易模拟），不在磁盘 IO
   → 即使全在 SATA SSD 上，IO 也不是瓶颈

5. 极端场景：全市场分钟级因子挖掘（批量扫描）
   → 如果真遇到 IO 瓶颈，临时把对应 chunk 移回 NVMe（一条 SQL）：
   ALTER TABLE bars_stock_zh_a_1min_nf
     SET TABLESPACE pg_default;  -- 移回 NVMe 默认表空间
   → 跑完再移回去
```

---

## 五、备份方案

### 5.1 备份策略

| 数据 | 方法 | 频率 | 存储位置 | 保留 |
|------|------|------|---------|------|
| PostgreSQL 全量 | `pg_basebackup` | 每周日 | 8TB SATA SSD | 4 份（1 个月） |
| PostgreSQL WAL | `archive_command` 连续归档 | 实时 | 8TB SATA SSD | 7 天 |
| Neo4j | `neo4j-admin dump` + rsync | 每日 | 8TB SATA SSD（从 VM1 传到 VM2） | 7 份 |
| MinIO | — | — | — | MinIO 本身有纠删码，暂不额外备份 |

### 5.2 PostgreSQL 备份配置

```bash
# ── postgresql.conf (VM2) ──────────────────────────────────────

# WAL 归档（支持 Point-in-Time Recovery）
wal_level = replica
archive_mode = on
archive_command = 'cp %p /sata8t/backups/pg_wal_archive/%f'

# 保留足够的 WAL 支持 PITR
wal_keep_size = '2GB'
```

```bash
# ── 每周全量备份脚本 (cron @weekly on VM2) ─────────────────────

#!/bin/bash
# /sata8t/scripts/pg_backup_full.sh

BACKUP_DIR="/sata8t/backups/pg_basebackup"
DATE=$(date +%Y%m%d_%H%M%S)

# 全量备份（压缩）
pg_basebackup -h localhost -U postgres \
  -D "${BACKUP_DIR}/base_${DATE}" \
  -Ft -z -P

# 保留最近 4 份，删除旧的
cd "${BACKUP_DIR}"
ls -dt base_* | tail -n +5 | xargs rm -rf

echo "[$(date)] Full backup completed: base_${DATE}"
```

```bash
# ── 清理旧 WAL 归档 (cron @daily on VM2) ──────────────────────

#!/bin/bash
# /sata8t/scripts/pg_wal_cleanup.sh

# 保留 7 天的 WAL 归档
find /sata8t/backups/pg_wal_archive -name "*.backup" -mtime +7 -delete
find /sata8t/backups/pg_wal_archive -type f -mtime +7 -delete
```

### 5.3 Neo4j 备份配置

```bash
# ── Neo4j 每日备份 (cron @daily on VM1) ────────────────────────

#!/bin/bash
# /opt/scripts/neo4j_backup.sh

DATE=$(date +%Y%m%d)
DUMP_FILE="/tmp/neo4j_dump_${DATE}.dump"

# 停止写入（或用 neo4j-admin database dump --to-stdout）
docker exec neo4j neo4j-admin database dump neo4j --to-path=/tmp/
docker cp neo4j:/tmp/neo4j.dump "${DUMP_FILE}"

# rsync 到 VM2 的 8TB SATA SSD
rsync -avz "${DUMP_FILE}" vm2:/sata8t/backups/neo4j_dump/

# 清理本地临时文件
rm -f "${DUMP_FILE}"

# 保留 7 天
ssh vm2 'find /sata8t/backups/neo4j_dump -name "*.dump" -mtime +7 -delete'
```

### 5.4 灾难恢复（PITR）

```bash
# ── 恢复到指定时间点 ───────────────────────────────────────────

# 1. 停止 PostgreSQL
systemctl stop postgresql

# 2. 恢复全量备份
rm -rf /nvme/pgdata/*
tar xzf /sata8t/backups/pg_basebackup/base_XXXXXXXX.tar.gz -C /nvme/pgdata/

# 3. 配置恢复目标时间
cat > /nvme/pgdata/recovery.signal <<EOF
EOF

cat >> /nvme/pgdata/postgresql.auto.conf <<EOF
restore_command = 'cp /sata8t/backups/pg_wal_archive/%f %p'
recovery_target_time = '2026-04-29 10:00:00'
EOF

# 4. 启动 PostgreSQL（自动应用 WAL 到目标时间点）
systemctl start postgresql
```

### 5.5 备份空间估算

| 数据 | 大小 | 备份开销 |
|------|------|---------|
| PostgreSQL 全量 (压缩) | ~50 GB (初期) → ~200 GB (2年后) | 4 份 × 200 GB = 800 GB (最大) |
| WAL 归档 (7天) | ~20-50 GB | 50 GB |
| Neo4j dump (7天) | ~1 GB × 7 | 7 GB |
| MySQL 快照 (迁移前保留) | ~50 GB | 50 GB |
| **总计** | | **~300-900 GB** |

→ 备份 + 温/冷数据 + 数据湖，8TB SATA SSD 的使用分配详见第四章 4.3 节。

---

## 六、MySQL → PostgreSQL 迁移操作手册

### 6.1 迁移步骤（在 VM2 上执行）

```bash
# Step 1: 安装 PostgreSQL 16 + 扩展（与 MySQL 共存）
sudo apt install postgresql-16 postgresql-16-timescaledb postgresql-16-pgvector
sudo systemctl start postgresql

# Step 2: 创建数据库和 schema
sudo -u postgres psql <<EOF
CREATE DATABASE chaos_db;
\c chaos_db
CREATE SCHEMA kg;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
EOF

# Step 3: 先建 atlas 的 kg.* 表（不依赖迁移）
sudo -u postgres psql -d chaos_db -f /path/to/atlas/migrations/001_kg_tables.sql

# Step 4: 用 pgloader 迁移 MySQL 数据到 public schema
pgloader mysql://user:pass@localhost/chaos_mysql \
         postgresql://postgres@localhost/chaos_db

# Step 5: 验证数据一致性
# 对比行数、抽样对比数据

# Step 6: phoenixA 切换驱动
# 修改配置 → 重启 phoenixA → 验证 API

# Step 7: 停掉 MySQL（或保留只读一段时间）
sudo systemctl stop mysql

# Step 8: K 线表转 TimescaleDB
sudo -u postgres psql -d chaos_db <<EOF
-- 日线：留 NVMe 默认表空间
SELECT create_hypertable('bars_stock_zh_a_daily_nf', 'trade_date',
  migrate_data => true,
  chunk_time_interval => INTERVAL '1 month'
);

-- 创建 SATA SSD 表空间（分钟线用）
CREATE TABLESPACE warm_storage LOCATION '/sata8t/pgdata_warm';

-- 分钟线：建在 SATA SSD 上
CREATE TABLE bars_stock_zh_a_1min_nf (...) TABLESPACE warm_storage;
SELECT create_hypertable('bars_stock_zh_a_1min_nf', 'trade_date',
  chunk_time_interval => INTERVAL '1 week'
);
ALTER TABLE bars_stock_zh_a_1min_nf SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'symbol',
  timescaledb.compress_orderby = 'trade_date DESC'
);
SELECT add_compression_policy('bars_stock_zh_a_1min_nf', INTERVAL '3 months');
EOF
```

---

## 七、实施路线

| 阶段 | 时间 | 内容 |
|------|------|------|
| **Phase A** | 现在 | VM2 装 PostgreSQL，建 kg.* 表，atlas 先用 |
| **Phase B** | Atlas Phase 1 完成后 | pgloader 迁移 MySQL → PostgreSQL |
| **Phase C** | 迁移验证后 | phoenixA 切 PG driver，停 MySQL |
| **Phase D** | Phase C 后 | K 线转 TimescaleDB，启用压缩+冷热分层 |
| **Phase E** | 按需 | PGVector 启用，文档 embedding |
| **Phase F** | 按需 | Kafka + Flink（用预留的 16GB RAM） |

---

## 附录：决策记录

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| 1 | PostgreSQL + TimescaleDB + PGVector 统一引擎 | 一套运维覆盖关系/时序/向量 | 2026-04-29 |
| 2 | 不引入 ClickHouse/Qdrant | 当前数据量不需要，避免运维复杂度 | 2026-04-29 |
| 3 | 3 VM 方案（服务/数据库/开发 分离） | 复用现有 VM 结构，IO 和内存隔离 | 2026-04-29 |
| 4 | 1 个 PostgreSQL 实例，schema 隔离 | 1 份内存/备份/连接池，可跨 schema JOIN | 2026-04-29 |
| 5 | NVMe 放热数据（日线/KG/向量），8TB 放分钟线全量+温存储+备份+数据湖 | 分钟线顺序读不需 NVMe；KNN/JSONB 随机读需 NVMe | 2026-04-29 |
| 6 | Neo4j 放 VM1（服务 VM） | atlas 专属，全球规模 ~5-30GB，直连最快 | 2026-04-29 |
| 7 | 预留 16GB RAM 给 Kafka/Flink | 不提前引入，留扩容空间 | 2026-04-29 |
| 8 | 分钟线全量放 SATA SSD，不做 NVMe↔SATA 冷热迁移 | 简化运维，顺序读 SATA 够用 | 2026-04-29 |
| 9 | 图谱+向量按全球产业链规模估算（不只 A 股） | 产业链全球化，NVIDIA/地缘政治影响 A 股 | 2026-04-29 |

