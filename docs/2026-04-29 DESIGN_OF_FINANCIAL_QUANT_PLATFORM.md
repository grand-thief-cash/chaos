# Chaos 金融量化平台 — 总体设计

## 系统全景

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           cthulhu (Angular)                             │
│                    前端：行情/图谱/回测/洞察                             │
└─────────┬────────────────┬────────────────┬────────────────┬────────────┘
          │                │                │                │
┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
│   phoenixA     │ │   artemis    │ │    atlas     │ │   cronjob    │
│   (Go)         │ │   (Python)   │ │   (Python)   │ │   (Go)       │
│   数据中台      │ │   行情拉取    │ │  知识图谱     │ │   调度中心    │
│   金融数据      │ │   回测引擎    │ │  影响引擎     │ │   定时任务    │
└───────┬────────┘ └──────────────┘ └──────┬───────┘ └──────────────┘
        │                                  │
        │              ┌───────────────────┘
        │              │
┌───────▼──────────────▼───────────────────────────────────────────────┐
│                    基础设施层                                         │
│                                                                      │
│  ┌──────────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ PostgreSQL 16    │  │ Neo4j    │  │ MinIO    │  │ LLM API  │    │
│  │ + TimescaleDB    │  │ (图谱)   │  │ (2.7TB)  │  │ GPT-4o   │    │
│  │ + PGVector       │  │          │  │          │  │          │    │
│  │ (统一数据引擎)    │  │          │  │          │  │          │    │
│  └──────────────────┘  └──────────┘  └──────────┘  └──────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## 物理部署

```
Dell R730  |  双路 E5-2683 v4 (32C/64T)  |  128 GB RAM

VM1 服务 VM (48GB)          VM2 数据库 VM (48GB)         VM3 开发机 (16GB)
┌───────────────────┐      ┌────────────────────────┐   ┌──────────┐
│ Docker Compose    │      │ PostgreSQL 16          │   │ 开发环境  │
│ ├ phoenixA        │◄────►│   + TimescaleDB        │   │          │
│ ├ atlas           │      │   + PGVector           │   └──────────┘
│ ├ artemis         │      │ 2TB NVMe (热)          │
│ ├ cronjob         │      │ 8TB SATA SSD (冷+备份) │   预留 16GB
│ ├ cthulhu         │      └────────────────────────┘   → Kafka/Flink
│ ├ neo4j           │
│ └ minio (2.7TB)   │
│ 512GB NVMe        │
└───────────────────┘
```

详细基础设施规划见：[2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md](./2026-04-29%20INFRASTRUCTURE_AND_DATA_ENGINE.md)

## 各服务定位

| 服务 | 职责 | 端口 |
|------|------|------|
| **phoenixA** (Go) | 数据中台：所有 DB 的 CRUD 网关，其他服务通过 HTTP 调用 | 18085 |
| **artemis** (Python) | 多源行情拉取、缓存、回测引擎 | 18000 |
| **atlas** (Python) | 产业链知识图谱、影响引擎、投资洞察 | 18400 |
| **cronjob** (Go) | 定时任务调度中心 | 19999 |
| **cthulhu** (Angular) | 前端 UI | 4200 |

## 服务交互

```
cronjob ─── HTTP ──→ atlas (POST /api/v1/pipeline/daily)
                       │
                       ├── HTTP ──→ phoenixA (CRUD kg.*)
                       ├── S3  ──→ MinIO (文档上传/下载)
                       ├── Bolt ──→ Neo4j (图谱读写)
                       └── HTTP ──→ LLM API (GPT-4o)

cthulhu ─── HTTP ──→ atlas (查询/分析/洞察)
cthulhu ─── HTTP ──→ phoenixA (行情/基础数据)

artemis ─── HTTP ──→ phoenixA (拉行情)
artemis ─── HTTP ──→ atlas (可选：查产业链辅助策略)
```

## 数据引擎策略

**统一使用 PostgreSQL 16 + 扩展**，覆盖所有数据场景：

| 场景 | 引擎/扩展 | 数据 |
|------|----------|------|
| 结构化元数据 | PostgreSQL 标准 | 文档、抽取结果、影响日志、证券注册、分类 |
| K 线行情（日线/分钟级） | TimescaleDB | OHLCV 时序数据，自动分区+压缩 |
| 语义搜索 | PGVector | 文档/公司名 embedding |
| 图谱 | Neo4j（独立） | 产业链关系网络（atlas 专属） |
| 文件存储 | MinIO（独立） | 财报/研报/新闻原始文件 |

> 不引入 ClickHouse / Qdrant — 当前数据量在 PostgreSQL 生态内可充分满足。
> 详细选型分析见：[2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md](./2026-04-29%20INFRASTRUCTURE_AND_DATA_ENGINE.md)

## Atlas 在平台中的位置

Atlas 是平台的 **投资决策辅助引擎**，与其他服务的关系：

- **cronjob → atlas**：每日定时触发新闻采集 + 影响分析 pipeline
- **atlas → phoenixA**：结构化数据 CRUD（documents, extractions, impact_logs）
- **phoenixA → atlas**：提供 security_registry 公司列表做 normalized_name 标准化
- **atlas → cthulhu**：提供知识图谱查询、事件影响、公司综述 API
- **artemis + atlas**：后续可实现事件驱动策略（事件影响 → 标的筛选 → 回测验证）

各服务详细设计见各自 docs/ 目录。

