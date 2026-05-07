# Atlas 产业链知识图谱引擎 — 系统设计

> 核心命题：**影响判断是否正确 + 是否早**，这才是系统的护城河。
>
> 图谱是手段，不是目的。
>
> 基础设施（VM / 存储 / 数据库引擎）见全局文档：[INFRASTRUCTURE_AND_DATA_ENGINE](../../../../docs/2026-04-29%20INFRASTRUCTURE_AND_DATA_ENGINE.md)

---

## 一、核心目标

一切设计围绕这两个能力：

### 能力一：事件 → 受影响公司

```
【事件】锂价上涨
→ 【上游】天齐锂业 → 利润↑（正面）
→ 【中游】宁德时代 → 电池成本↑（负面）
→ 【下游】比亚迪 → 整车成本↑（负面）
```

**要求**：每日自动运行，输出结构化的影响清单，按影响强度排序。

### 能力二：公司 → 产业链 + 发展 Review

```
宁德时代：
├── 产业链位置：中游（动力电池制造）
├── 上游依赖：锂、镍、钴（资源）
├── 核心产品：磷酸铁锂电池、三元锂电池
├── 下游客户：特斯拉、比亚迪、蔚来
├── 主要竞品：比亚迪弗迪电池（直接竞品）、LG新能源
├── 关键风险：锂价波动、欧盟碳关税
└── 近期事件影响：...
```

**要求**：任意输入一个公司名，自动聚合图谱数据 + LLM(DeepSeek) 生成综述。

### 四个维度

| 维度 | 说明 |
|------|------|
| **结构** | 图谱：公司-产品-资源-产业的关系网络 |
| **时间** | 时间序列：事件/关系随时间变化 |
| **推理** | 影响引擎：事件沿产业链传导计算 |
| **聚合** | 总结：LLM 生成投资视角的分析报告 |

---

## 二、Atlas 架构

```
┌──────────────────────────────────────────────────┐
│           应用层（Application）                   │
│   cthulhu 前端 / API 查询 / 投资洞察报告           │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│        推理层（Impact Engine）  ← 核心价值         │
│   事件解析 → 图谱传播 → 影响计算（规则+LLM）        │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│          图谱层（Graph + Index）                  │
│   Neo4j 知识图谱 + Graph Builder（去重/标准化）    │
└──────────┬────────────────────────┬──────────────┘
           │                        │
┌──────────▼──────────┐  ┌─────────▼──────────────┐
│ 数据层(phoenixA)     │  │ 文件层（MinIO）         │
│ PostgreSQL (JSONB)  │  │ 原始文档存储            │
│ 通过 HTTP API 访问   │ │ 直接 S3 协议访问       │
└─────────────────────┘  └────────────────────────┘
```

---

## 三、数据源分层与采集策略

> 知识图谱 ≠ 只读新闻。构建产业链图谱需要**多类型、多频率**的数据源。
> 不同数据源的作用不同：有的用来**建图谱结构**（供应链/产品/资源关系），有的用来**触发影响分析**（事件/政策）。

### 3.1 数据源分类

| 类型 | 来源 | 频率 | 主要作用 | 示例 |
|------|------|------|---------|------|
| **研报** | 券商研报、行业研报 | 每周/每月 | 🏗️ **建图谱**：产业链关系、竞品、上下游 | 中信证券新能源行业深度 |
| **财报** | 上市公司年报/季报 | 每季度 | 🏗️ **建图谱**：产品、客户、供应商、营收结构 | 宁德时代 2025 年报 |
| **行业分析** | 行业白皮书、产业链报告 | 低频 | 🏗️ **建图谱**：行业结构、技术路线、资源分布 | 锂电池产业链全景图 |
| **公司公告** | 交易所公告 | 每日 | 🏗️ 建图谱 + ⚡ 触发事件 | 并购、投资、产能扩张 |
| **政策文件** | 政府/监管机构 | 不定期 | ⚡ **触发事件**：关税、补贴、环保标准 | 欧盟碳关税法案 |
| **新闻** | RSS/新闻 API/爬虫 | 每日 | ⚡ **触发事件**：价格变动、供给变化、突发事件 | 锂价连续 3 日上涨 |
| **人工录入** | 手动补充 | 按需 | 🏗️ **建图谱**：关键关系修正、新实体 | 新增子公司、产品线调整 |

### 3.2 两类数据源的处理策略

```
┌─────────────────────────────────────────────────────────────────┐
│  🏗️ 图谱构建型（Graph-Building）                                │
│  目标：丰富/修正/更新知识图谱的节点和关系                         │
│  特点：低频、高信息密度、长文档、需要深度抽取                      │
│  来源：研报、财报、行业分析、公告（非事件类）                      │
│                                                                  │
│  处理流程：                                                      │
│  文档 → 切分 → LLM 抽取(DeepSeek) → 实体/关系 → Graph Builder   │
│  → 重点：供应链关系、产品线、资源依赖、竞品、技术路线              │
│  → 质量要求高，confidence 阈值 ≥ 0.6                              │
│  → 人工可审核关键关系                                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ⚡ 事件触发型（Event-Triggering）                               │
│  目标：识别新事件，触发影响分析                                    │
│  特点：高频、短文本、需要快速处理 + 事件去重                       │
│  来源：新闻、政策发布、公告（事件类）                              │
│                                                                  │
│  处理流程：                                                      │
│  新闻/政策 → 过滤(DeepSeek) → 抽取(DeepSeek) → ⭐事件去重        │
│  → 新事件 → Impact Engine → 影响清单                             │
│  → 已知事件 → 合并来源，不重复触发                                │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 分类治理：渐进式分类法

> ❓ **问题**：文档中涉及多种分类（事件类型、文档类型、关系类型等），如何保证不过细也不过粗？扩展时怎么办？
>
> ✅ **原则**：**先粗后细，配置驱动，`other` 兜底，数据驱动拆分。**

#### 分类管理策略

```
1️⃣ 所有分类定义放 YAML 配置，不硬编码
    → config/atlas.yaml 中定义枚举列表
    → 代码中只读取配置，不 hardcode 类型值
    → 新增/修改类型 = 改配置 + 重启，无需改代码逻辑

2️⃣ 每个分类体系保留 `other` 兜底
    → LLM 抽取时如果拿不准 → 标记 other
    → Graph Builder 遇到 other → 仍然入图，不丢数据

3️⃣ 定期审计 `other` 频率（第二期）
    → 统计 other 占比：如果 > 15% → 说明分类不够用
    → 查看 other 的 description，找出高频模式
    → 拆分出新类型（改配置即可）

4️⃣ LLM prompt 中列出可选类型 + 说明
    → prompt 里写清楚每个类型的含义和边界
    → LLM 选择最接近的类型（而不是自创类型）
    → 这样分类一致性由 prompt 控制
```

#### 各分类体系的当前粒度与扩展策略

| 分类体系 | 当前数量 | 粒度评估 | 扩展策略 |
|---------|---------|---------|---------|
| **文档类型** (doc_type) | 7 种 | ✅ 合适 | 按数据源自然扩展 |
| **事件类型** (event_type) | 15 种 | ✅ 合适 | 审计 `other` 频率再拆分 |
| **关系类型** (relationship) | 19 种 + other | ✅ 合适 | LLM 全量抽取，`other` 后续审计拆分 |
| **节点类型** (node label) | 8 种 | ✅ 合适 | 稳定，不太会频繁变 |

```yaml
# config/atlas.yaml — 分类定义（示例）
taxonomy:
  doc_types:
    - earnings       # 财报
    - research        # 研报
    - industry        # 行业分析
    - news            # 新闻
    - policy          # 政策
    - announcement    # 公告
    - manual          # 人工录入

  event_types:
    - price_change
    - supply_change
    - policy_new
    - policy_change
    - tariff_change
    - tech_breakthrough
    - capacity_change
    - merger_acquisition
    - investment
    - leadership_change
    - earnings_beat
    - earnings_miss
    - accident_disaster
    - sanction
    - other             # ← 兜底，定期审计

  # 关系类型：全部告诉 LLM，让它尽可能多抽取
  # LLM 抽取时不限制类型；Graph Builder 入图时全部写入
  # Impact Engine 推理时只沿供应链核心关系做 BFS（见第六章）
  relationship_types:
    # 产业链关系（Impact Engine 重度使用）
    - SUPPLIER_OF
    - CUSTOMER_OF
    - DEPENDS_ON_RESOURCE
    - CONSUMES_RESOURCE
    - PRODUCES_RESOURCE
    - EXTRACTS_RESOURCE
    - COMPETITOR_OF
    # 归属/结构关系
    - BELONGS_TO_INDUSTRY
    - OPERATES_IN_MARKET
    - PRODUCES
    - USES_TECHNOLOGY
    - OWNS_ASSET
    - SUBSIDIARY_OF
    - INVESTED_IN
    - PART_OF_PRODUCT
    - APPLIED_IN
    # 事件关系
    - INVOLVED_IN_EVENT
    - IMPACTED_BY_POLICY
    - IMPACT_ON
    # 兜底
    - OTHER               # ← LLM 识别到新关系类型时标记，定期审计
```

### 3.4 事件去重机制

> ❓ **核心问题**：同一个真实世界事件（如"锂价上涨"）可能被 20 篇新闻报道。
> `content_hash` 只能去重**完全相同**的文档，不同文章描述同一事件无法去重。
>
> ✅ **方案**：**事件指纹（Event Fingerprint）** — 将事件结构化后生成唯一标识。

#### 为什么用 Fingerprint 而不用 Embedding？

| 对比项 | Fingerprint（指纹） | Embedding（向量） |
|--------|-------------------|-----------------|
| **成本** | ✅ 零成本（hash 计算） | ❌ 需调 embedding API（额外费用） |
| **确定性** | ✅ 完全确定（相同输入 = 相同 hash） | ⚠️ 模糊匹配（阈值调优复杂） |
| **可解释** | ✅ 能看到为什么去重（entity+type 匹配） | ❌ 黑盒相似度 |
| **速度** | ✅ O(1) hash 查找 | ⚠️ 需要 KNN 搜索 |
| **适用场景** | 结构化事件（LLM 已抽取出类型/实体） | 自由文本模糊匹配 |
| **局限** | 边缘事件可能漏去重 | 阈值不好调，可能误去重 |

> **结论**：事件已经被 LLM 结构化了（entity + type + direction），
> 用 fingerprint 做主去重 = **零成本 + 确定性 + 可解释**。
> Embedding 语义兜底留到第二期，仅对 `other` 类型事件做补充。

#### 两层去重（第一期）

```
Layer 1️⃣ 文档级去重（已有）
    content_hash — 完全相同的文档不重复入库
    → 解决：同一篇文章被多次抓取

Layer 2️⃣ 事件指纹去重（核心）
    LLM 抽取事件后，生成结构化指纹：
    {
        entity: "锂",               ← 受影响实体（标准化后）
        event_type: "price_change",  ← 事件类型（枚举）
        direction: "up",             ← 变化方向
        time_bucket: "2026-W19"      ← 时间桶（周粒度）
    }
    → fingerprint = hash(entity + event_type + direction + time_bucket)
    → 同一周内、同一实体、同类型事件 → 视为同一事件

    事件类型枚举（见 3.3 config/atlas.yaml 中 event_types 定义）

Layer 3️⃣ 语义相似度兜底（第二期）
    对于 event_type = "other" 且指纹无法覆盖的边缘情况：
    → 新事件描述 vs 最近 7 天已有事件描述
    → 余弦相似度 > 0.85 → 视为重复 → 合并来源
    → 可用 DeepSeek embedding 或简单 TF-IDF
```

#### 事件去重流程

```
新闻/政策文档
    ↓
LLM 抽取 → 识别出事件列表
    ↓
对每个事件：
    ├── 生成 event_fingerprint
    ├── 查询 kg.events 表：是否存在相同 fingerprint + 近期时间？
    │   ├── YES → 已知事件
    │   │   ├── 追加 source_doc_id 到该事件
    │   │   ├── 更新 source_count
    │   │   ├── 如果新文章有增量信息 → 更新 description
    │   │   └── ❌ 不重复触发 Impact Engine
    │   │
    │   └── NO → 新事件
    │       ├── 创建 kg.events 记录
    │       ├── 关联 source_doc_ids
    │       └── ✅ 触发 Impact Engine
```

#### 时间桶策略

| 事件类型 | 时间桶粒度 | 理由 |
|---------|-----------|------|
| price_change | **周** | 价格趋势多日延续，同一波行情算一个事件 |
| policy_new / tariff_change | **月** | 政策发布后多日报道，不应重复 |
| accident_disaster | **日** | 突发事件时效性强 |
| merger_acquisition | **月** | 并购消息反复报道 |
| earnings_beat/miss | **季度** | 同一季财报只算一次 |
| 其他 | **周** | 默认 |

---

## 四、数据层设计

### 设计原则

> ❗ 抽取结果必须先持久化到 PostgreSQL（通过 phoenixA），再通过 Graph Builder 写入图谱。
>
> 原因：**可回溯 + 可重跑 + 可调 prompt**。

### 4.1 数据访问策略

Atlas 的结构化元数据通过 phoenixA HTTP API 访问，不直接连数据库：

```
atlas                     phoenixA                    PostgreSQL (kg schema)
  │                          │                            │
  │ POST /api/v1/kg/         │                            │
  │   documents              │ INSERT INTO kg.documents   │
  │ ─────────────────────→   │ ─────────────────────────→ │
  │                          │                            │
  │ GET /api/v1/kg/          │                            │
  │   extractions?doc_id=xx  │ SELECT FROM kg.extractions │
  │ ─────────────────────→   │ ─────────────────────────→ │

atlas 直接访问（不经过 phoenixA）：
  │───→ Neo4j（图谱，atlas 专属内部存储）
  │───→ MinIO（文档文件，S3 协议）
  │───→ LLM API（DeepSeek V4-Flash / V4-Pro）
```

| 数据 | 走 phoenixA | 原因 |
|------|------------|------|
| documents / extractions / impact_logs / events | ✅ | 结构化元数据，复用数据中台 |
| daily_runs | ✅ | 运行日志 |
| Neo4j 图谱 | ❌ 直连 | Cypher 查询太领域化，不适合通用 API |
| MinIO 文件 | ❌ 直连 | S3 协议直连 |

**对 phoenixA 的影响**：新增 `kg` 数据域，与 `bars` / `reference` / `taxonomy` 并列。

### 4.2 原始文档存储 → MinIO

```
MinIO
├── atlas-documents/         ← atlas 专用 bucket
│   ├── earnings/            # 财报 PDF（年报/季报）
│   ├── research/            # 券商研报 / 行业研报 PDF
│   ├── industry/            # 行业白皮书 / 产业链分析
│   ├── news/                # 新闻文本
│   ├── policy/              # 政策文件 / 法规
│   ├── announcements/       # 公司公告
│   └── manual/              # 人工录入的补充材料
```

- S3 协议直连（`boto3` / `minio-py`）
- `documents` 表只存 `file_path`（MinIO 对象路径），不存文件本身

### 4.3 PostgreSQL 表设计（kg schema）

```sql
-- ① 文档元数据
CREATE TABLE kg.documents (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       VARCHAR(64) UNIQUE NOT NULL,
    title        VARCHAR(512),
    doc_type     VARCHAR(32) NOT NULL,            -- earnings|research|industry|news|policy|announcement|manual
    source_type  VARCHAR(16) NOT NULL DEFAULT 'event',  -- graph_building|event_triggering
    company      VARCHAR(128),
    publish_time TIMESTAMP,
    file_path    VARCHAR(1024),                    -- MinIO 对象路径
    content_hash VARCHAR(64),                      -- 去重（Layer 1）
    processed    BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ② 抽取结果（JSONB 可回溯，核心表）
CREATE TABLE kg.extractions (
    id             BIGSERIAL PRIMARY KEY,
    doc_id         VARCHAR(64) NOT NULL REFERENCES kg.documents(doc_id),
    chunk_index    INT NOT NULL,
    prompt_version VARCHAR(16) NOT NULL,            -- v5, v6... 追踪 prompt 版本
    llm_model      VARCHAR(64),
    graph_json     JSONB NOT NULL,                   -- 完整抽取 JSON（对应 skill 输出）
    input_tokens   INT,
    output_tokens  INT,
    cost_usd       DECIMAL(10,6),
    quality_score  FLOAT,
    status         VARCHAR(16) DEFAULT 'completed',
    created_at     TIMESTAMP DEFAULT NOW(),
    UNIQUE(doc_id, chunk_index, prompt_version)
);

-- ③ 规范化事件表（事件去重核心，Layer 2）
CREATE TABLE kg.events (
    id               BIGSERIAL PRIMARY KEY,
    event_fingerprint VARCHAR(64) UNIQUE NOT NULL,  -- hash(entity+type+direction+time_bucket)
    entity_name      VARCHAR(256) NOT NULL,          -- 受影响实体（标准化后）
    event_type       VARCHAR(32) NOT NULL,           -- price_change|supply_change|policy_new|...
    direction        VARCHAR(16),                     -- up|down|neutral|new|removed
    time_bucket      VARCHAR(16) NOT NULL,           -- 2026-W19 / 2026-05 / 2026-Q2
    description      TEXT,                            -- 事件摘要（可随新来源更新）
    severity         VARCHAR(8) DEFAULT 'medium',     -- high|medium|low
    source_doc_ids   VARCHAR(64)[] NOT NULL,          -- 所有报道该事件的文档
    source_count     INT DEFAULT 1,                   -- 被多少篇文档报道（热度指标）
    first_seen_at    TIMESTAMP DEFAULT NOW(),         -- 首次发现时间
    last_seen_at     TIMESTAMP DEFAULT NOW(),         -- 最近一次被报道
    impact_triggered BOOLEAN DEFAULT FALSE,           -- 是否已触发 Impact Engine
    created_at       TIMESTAMP DEFAULT NOW()
);

-- ④ 图谱写入记录
CREATE TABLE kg.graph_ingestions (
    id              BIGSERIAL PRIMARY KEY,
    extraction_id   BIGINT REFERENCES kg.extractions(id),
    nodes_created   INT DEFAULT 0,
    edges_created   INT DEFAULT 0,
    nodes_merged    INT DEFAULT 0,
    ingested_at     TIMESTAMP DEFAULT NOW()
);

-- ⑤ 每日流水线记录
CREATE TABLE kg.daily_runs (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    docs_fetched     INT DEFAULT 0,                  -- 抓取的文档总数
    docs_graph_building INT DEFAULT 0,               -- 图谱构建类文档数
    docs_event       INT DEFAULT 0,                  -- 事件类文档数
    events_new       INT DEFAULT 0,                  -- 新事件数
    events_deduped   INT DEFAULT 0,                  -- 被去重的事件数
    extractions_ok   INT DEFAULT 0,
    extractions_fail INT DEFAULT 0,
    impacts_generated INT DEFAULT 0,
    total_cost_usd   DECIMAL(10,4),
    status           VARCHAR(16),
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP
);

-- ⑥ 影响日志（推理结果持久化）
CREATE TABLE kg.impact_logs (
    id            BIGSERIAL PRIMARY KEY,
    event_id      BIGINT REFERENCES kg.events(id),   -- 关联到规范化事件
    event_name    VARCHAR(512),
    event_time    VARCHAR(32),
    source_doc_id VARCHAR(64),
    impact_json   JSONB NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);
```

### 4.4 phoenixA 需要新增的 API

```
POST   /api/v1/kg/documents                  # 创建文档记录
GET    /api/v1/kg/documents                  # 列表查询（支持 doc_type/source_type 过滤）
GET    /api/v1/kg/documents/{doc_id}         # 查询单个
PUT    /api/v1/kg/documents/{doc_id}         # 更新状态

POST   /api/v1/kg/extractions                # 存储抽取结果
GET    /api/v1/kg/extractions                # 按 doc_id/prompt_version 查询
GET    /api/v1/kg/extractions/{id}           # 单条详情

POST   /api/v1/kg/events                     # 创建/去重事件
GET    /api/v1/kg/events                     # 按 fingerprint/时间/类型 查询
GET    /api/v1/kg/events/{id}                # 单条详情
PUT    /api/v1/kg/events/{id}                # 更新（追加来源、更新描述）
GET    /api/v1/kg/events/recent              # 最近 N 天事件（去重后用于展示）

POST   /api/v1/kg/graph-ingestions           # 记录入图操作
POST   /api/v1/kg/daily-runs                 # 记录每日运行
GET    /api/v1/kg/daily-runs                 # 查看历史

POST   /api/v1/kg/impact-logs                # 存储影响分析结果
GET    /api/v1/kg/impact-logs                # 按事件/时间查询
```

---

## 五、图谱层设计

### 5.1 Graph Builder

> ⚠️ **不要直接用抽取结果写图。** 需要独立的 Graph Builder 做去重/标准化/质量过滤。

```
extractions（通过 phoenixA API 读取 graph_json）
    ↓
Entity Resolution（实体解析）
    ├── 公司：normalized_name 精确匹配 + 模糊匹配
    │         对照 phoenixA 的 security_registry 做标准化
    ├── 产品：standard_name 匹配
    ├── 资源：name 匹配
    └── 不确定的 → 标记待人工确认
    ↓
Quality Gate（质量门控）
    ├── confidence < 0.5 → 丢弃或标记 low_quality
    ├── 无 evidence → 标记 no_evidence
    └── is_inferred = true → 标记推测
    ↓
MERGE into Neo4j
    ├── 已存在 → 更新属性 + 合并 source_doc_ids 列表
    └── 不存在 → 创建新节点/边
    ↓
记录到 graph_ingestions（通过 phoenixA API）
```

### 5.2 Neo4j 存储策略

**只存高质量、可推理的数据**：

| 存 ✅ | 不存 ❌ |
|-------|---------|
| 公司节点（去重后的） | 原始 evidence 全文 |
| 产品/资源/技术节点 | 每个 chunk 的 source 详情 |
| 供应链关系 | 低 confidence 的推测关系 |
| 竞品关系 | LLM 原始输出 |
| 资源依赖关系 | |
| 事件/政策节点 + IMPACT_ON 边 | |

> evidence 和 source 详情留在 PostgreSQL `kg.extractions.graph_json` 中，
> Neo4j 只保留 `source_doc_ids[]`，需要时回查 phoenixA API。

### 5.3 节点模型

```
(:Company {
    normalized_name,        -- 唯一键
    name, ticker, country,
    value_chain_position,   -- upstream|midstream|downstream
    source_doc_ids[],
    last_updated
})

(:Product    { name, standard_name, category, source_doc_ids[] })
(:Resource   { name, category, price_trend, supply_status, scarcity })
(:Industry   { name })
(:Technology { name })
(:Asset      { name, type, owner })
(:Event      { name, type, impact_scope, time })
(:Policy     { name, type, impact_scope, time })
(:Market     { name })
```

### 5.4 关系类型（19 种）

**产业链关系**（推理引擎重度使用）：
- `SUPPLIER_OF`, `CUSTOMER_OF` — 供应链核心
- `DEPENDS_ON_RESOURCE`, `CONSUMES_RESOURCE`, `PRODUCES_RESOURCE`, `EXTRACTS_RESOURCE` — 资源链
- `COMPETITOR_OF {product, competition_type, dimension}` — 竞品

**归属关系**：
- `BELONGS_TO_INDUSTRY`, `OPERATES_IN_MARKET`, `PRODUCES`
- `USES_TECHNOLOGY`, `OWNS_ASSET`, `SUBSIDIARY_OF`, `INVESTED_IN`
- `PART_OF_PRODUCT`, `APPLIED_IN`

**事件关系**：
- `INVOLVED_IN_EVENT`, `IMPACTED_BY_POLICY`
- `IMPACT_ON {impact_direction, impact_type, impact_strength, transmission_path}`

所有关系附带：`{value_chain_position, confidence, time, source_doc_ids[]}`

---

## 六、推理层 — Impact Engine

> 系统的 Alpha 核心。图谱人人能建，影响判断的准确性和速度决定投资价值。

### 6.1 三步推理法

```
输入：一个事件（新闻/政策/财报数据）

Step 1️⃣ 事件解析（Event Parsing）
    LLM 将事件解析为结构化影响对象：
    "锂价上涨" → {
        affected_entity: "锂",
        entity_type: "resource",
        change: "price_trend: up",
        scope: "industry"
    }

Step 2️⃣ 图谱传播（Graph Traversal）
    从影响对象出发，沿供应链关系做 BFS（1-3 层）：
    Resource:锂
      ← DEPENDS_ON_RESOURCE ← Company:宁德时代（中游）
        ← SUPPLIER_OF ← Company:比亚迪（下游）
      ← EXTRACTS_RESOURCE ← Company:天齐锂业（上游）

Step 3️⃣ 影响计算（Impact Calculation）
    规则引擎（优先） + LLM 补充推理：

    ┌─────────────────────────────────────────────────┐
    │ IF resource.price_trend == "up":                │
    │   上游（extracts/produces） → positive (revenue) │
    │   中下游（depends/consumes） → negative (cost)   │
    │                                                  │
    │ IF resource.supply_status == "tight":            │
    │   拥有该资源的公司 → positive (supply advantage)  │
    │   依赖该资源的公司 → negative (supply risk)       │
    │                                                  │
    │ IF policy.type == "tariff_increase":             │
    │   出口导向公司 → negative (revenue)               │
    │   国内替代公司 → positive (demand)                │
    └─────────────────────────────────────────────────┘

    LLM 补充：对规则无法覆盖的复杂事件，用 LLM 推理

输出：
[
    {company: "天齐锂业", direction: "positive", type: "revenue",
     strength: "high", path: "锂价↑ → 锂矿利润↑"},
    {company: "宁德时代", direction: "negative", type: "cost",
     strength: "high", path: "锂价↑ → 电池成本↑"},
    {company: "比亚迪",   direction: "negative", type: "cost",
     strength: "medium", path: "锂价↑ → 电池成本↑ → 整车成本↑"},
]
```

### 6.2 规则引擎 vs LLM 的分工

| 场景 | 方法 | 理由 |
|------|------|------|
| 资源价格变动 | **规则** | 逻辑清晰、可预测 |
| 供给紧张/过剩 | **规则** | 方向确定 |
| 关税/贸易政策 | **规则 + LLM** | 规则定方向，LLM 补路径 |
| 技术突破/并购 | **LLM** | 影响复杂，需要推理 |
| 宏观政策（加息/降息） | **规则 + LLM** | 传导路径多元 |
| 突发事件（事故/灾害） | **LLM** | 需要上下文理解 |

### 6.3 影响强度评分

```
strength_score = base_score × distance_decay × confidence

- base_score: 事件影响程度（high=3, medium=2, low=1）
- distance_decay: 0.7^hop（每层衰减 30%）
- confidence: 影响路径上所有关系 confidence 的乘积

映射：
- score ≥ 2.0 → high
- score ≥ 1.0 → medium
- score < 1.0 → low
```

### 6.4 影响输出持久化

每次推理结果存到 `kg.impact_logs`（通过 phoenixA API），用于：
1. 回溯验证（事后看是否判断正确）
2. 趋势分析（同一公司历史受影响次数/方向）
3. 模型迭代（用历史结果调优规则）

---

## 七、服务设计

### 7.1 Atlas 作为独立服务，不拆分

**结论：1 个 Python(FastAPI) 进程，3 个逻辑模块。**

**为什么不合并到 phoenixA？**

| 考虑 | 分析 |
|------|------|
| 语言不同 | phoenixA = Go，atlas = Python |
| 职责不同 | phoenixA = 通用 CRUD 中台；atlas = 领域推理引擎 |
| 依赖不同 | atlas 需要 Neo4j、LLM API、PDF 解析 |
| 发布节奏 | atlas 频繁迭代（调 prompt、调规则） |

**为什么不拆微服务？**

| 考虑 | 分析 |
|------|------|
| 个人开发者 | 3 服务 = 3 倍运维 |
| 数据流 | 三模块紧密耦合 |
| 性能 | 瓶颈在 LLM API IO，不在进程通信 |
| 可扩展 | 代码已按模块组织，需要时可拆 |

### 7.2 Atlas 内部模块

```
atlas (一个 FastAPI 进程)
│
├── Ingestion 模块
│   ├── 文档上传 → MinIO + phoenixA(documents)
│   ├── PDF/HTML 解析 + 切分
│   ├── 新闻拉取
│   ├── 研报/政策/行业分析 采集
│   └── 文档分类（graph_building / event_triggering）
│
├── Extraction 模块
│   ├── LLM 调用 (skill v5) — V4-Flash / V4-Pro
│   ├── Pydantic 校验
│   ├── 结果存 phoenixA(extractions)
│   ├── Graph Builder → Neo4j
│   └── 事件抽取 + 事件去重 → phoenixA(events)
│
└── Reasoning 模块 ← 核心
    ├── 事件解析 (LLM)
    ├── 图谱传播 (Neo4j BFS)
    ├── 影响计算 (规则 + LLM)
    ├── 公司综述 (聚合 + LLM)
    └── 结果存 phoenixA(impact_logs)
```

---

## 八、计算触发机制

### 8.1 两种模式

```
模式 A：事件驱动（实时性）
  新文档上传 → 抽取 → 存 phoenixA → Graph Builder → Neo4j
  → [若含事件/政策] → 事件去重 → [新事件] → 自动触发 Impact Engine

模式 B：每日批处理（稳定性，主模式）
  Cron 08:00 触发：
    1. 拉取昨日~今晨新闻 + 新发布的政策/公告
    2. 过滤相关性（DeepSeek，低成本）
    3. 分类：graph_building vs event_triggering
    4. LLM 抽取（DeepSeek + skill v5）
    5. 存 phoenixA(extractions)
    6. Graph Builder → Neo4j（图谱构建类文档更新图谱）
    7. 事件去重 → kg.events（事件类文档）
    8. 新事件 → Impact Engine（规则+LLM）
    9. 输出「今日影响清单」
   10. 存 phoenixA(impact_logs)

模式 C：周期性图谱充实（低频）
  每周/每月：
    1. 拉取新发布的研报 / 行业分析
    2. 深度抽取：供应链关系、产品线、竞品
    3. Graph Builder → 充实/修正图谱结构
    → 无需触发 Impact Engine
```

### 8.2 流水线编排

```
── 每日流水线 ──────────────────────────────────────────────────

┌────────────┐    ┌────────────┐    ┌──────────────┐    ┌──────────────┐
│ Fetch Docs │───→│  Filter    │───→│  Classify    │───→│  Extract     │
│(news/policy│    │(DeepSeek)  │    │(graph_build/ │    │ (DeepSeek    │
│ /announce) │    │            │    │ event_trigger)│    │  + skill)    │
└────────────┘    └────────────┘    └──────┬───────┘    └──────┬───────┘
                                           │                    │
                            ┌──────────────┘                    │
                            ▼                                   ▼
                  ┌──────────────┐                     ┌──────────────┐
                  │Graph Builder │                     │  phoenixA    │
                  │  → Neo4j     │                     │ (extractions)│
                  │(图谱结构更新) │                     └──────┬───────┘
                  └──────────────┘                            │
                                                       ┌──────▼───────┐
┌─────────────┐    ┌──────────────┐    ┌────────────┐  │ Event Dedup  │
│ phoenixA    │←───│ Impact Calc  │←───│Event Parse  │←─│ → kg.events  │
│(impact_logs)│    │ (规则+LLM)   │    │+ Graph BFS │  │(仅新事件触发)│
└──────┬──────┘    └──────────────┘    └────────────┘  └──────────────┘
       │
┌──────▼──────┐
│ 今日洞察报告 │
└─────────────┘

── 周期性图谱充实 ──────────────────────────────────────────────

┌────────────┐    ┌──────────────┐    ┌──────────────┐
│Fetch Reports│──→│ Deep Extract │──→│ Graph Builder │
│(研报/行业   │   │ (DeepSeek)   │   │   → Neo4j     │
│ 分析/白皮书)│   │  供应链/产品  │   │ (充实图谱结构)│
└────────────┘    └──────────────┘    └──────────────┘
```

---

## 九、技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 服务框架 | **FastAPI** (Python) | 异步、与 artemis 同栈 |
| 元数据存储 | **PostgreSQL JSONB** (通过 phoenixA) | 可回溯、JSONB 查询 |
| 图数据库 | **Neo4j Community 5.x** (直连) | 免费、Cypher 直观 |
| 文件存储 | **MinIO** (S3 协议) | 已有基础设施 |
| LLM | **litellm** → DeepSeek V4-Flash (主力) + V4-Pro (复杂推理) | 双模型阶梯，**月成本 ~$8-10**（见 9.1） |
| 文档解析 | **PyMuPDF + BeautifulSoup** | 轻量 |
| 定时调度 | **cronjob** (已有 Go 服务) | 不新增组件 |

### 9.1 LLM 选型：DeepSeek V4 双模型策略

> **选 DeepSeek 的核心原因：成本极低 + 中文能力强 + 1M 上下文。**
>
> DeepSeek V4 系列（2026-04-24 发布）提供两个模型，形成**性价比阶梯**：

#### DeepSeek V4 模型对比

| 对比项 | V4-Flash（干活主力） | V4-Pro（复杂推理） | GPT-4o（参考） |
|--------|--------------------|--------------------|---------------|
| **定位** | 高性价比，日常任务 | 顶级推理，复杂分析 | — |
| **参数** | 2840B (MoE, 激活 130B) | 16000B (MoE, 激活 490B) | — |
| **上下文** | **1M tokens** | **1M tokens** | 128K |
| **输入价格** | **$0.14/1M** | $1.74/1M | $2.5/1M |
| **输出价格** | **$0.28/1M** | $3.48/1M | $10/1M |
| **缓存读取** | **$0.028/1M** | $0.145/1M | — |
| **中文能力** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **MMLU Pro** | 86.4 (13/124) | 87.5 (9/124) | — |
| **SWE-bench** | 79.0 (15/103) | 80.6 (7/103) | — |
| **LiveCodeBench** | 91.6 (4/118) | 93.5 (1/118) | — |

> **关键发现**：V4-Flash 性能只比 V4-Pro 低 2-5%，但价格便宜 **12x**。
> Atlas 绝大多数任务用 V4-Flash 足够，仅复杂推理用 V4-Pro。

#### 分层使用策略

| 任务 | 模型 | 模式 | 理由 |
|------|------|------|------|
| 新闻过滤（相关性判断） | **V4-Flash** | 常规 | 简单二分类，最便宜 |
| 文档抽取（实体/关系） | **V4-Flash** | 高(High) | 核心任务，思考模式提升抽取质量 |
| 事件解析 + 指纹生成 | **V4-Flash** | 常规 | 结构化输出，模板任务 |
| 公司综述生成 | **V4-Flash** | 常规 | 聚合文本生成 |
| 复杂推理（多跳影响传导） | **V4-Pro** | 高(High) | 需深度 chain-of-thought |
| 规则无法覆盖的事件分析 | **V4-Pro** | 高(High) | 复杂语境理解 |

> 📌 **1M 上下文的价值**：研报/年报动辄几万字，以前必须切分再抽取。
> V4 的 1M 窗口意味着很多文档可以**整篇扔进去**，减少切分逻辑复杂度，
> 抽取质量也更高（LLM 看到全文上下文）。但仍建议对超长文档做切分，
> 因为整篇输入 token 量大 → 成本上升。需要在质量和成本间找平衡。

#### Prompt 缓存策略

> V4 支持 **Prompt 缓存**（有效期 1 天）：相同 system prompt 的后续请求，输入价格降到缓存读取价。

| 模型 | 正常输入 | 缓存读取 | 节省 |
|------|---------|---------|------|
| V4-Flash | $0.14/1M | **$0.028/1M** | **80%** |
| V4-Pro | $1.74/1M | **$0.145/1M** | **92%** |

**利用方式**：
- Atlas 的抽取 prompt（skill v5）是固定的 system prompt → 天然适合缓存
- 每日批处理中，同一个 system prompt 处理 100+ 文档 → 第一篇正常计费，后续全命中缓存
- **实际日常成本可再降 50-70%**

#### 通过 litellm 调用（保持切换灵活性）

```python
# atlas/connectors/llm_client.py
import litellm

# DeepSeek V4 配置
litellm.api_key = config.deepseek_api_key
litellm.api_base = "https://api.deepseek.com"

# V4-Flash — 日常任务（过滤/抽取/事件解析/综述）
response = litellm.completion(
    model="deepseek/deepseek-v4-flash",      # V4-Flash
    messages=[...],
    response_format={"type": "json_object"},
)

# V4-Flash — 思考模式（需要更高质量的抽取）
response = litellm.completion(
    model="deepseek/deepseek-v4-flash",
    messages=[...],
    thinking={"type": "enabled", "budget_tokens": 4096},  # 启用思考
)

# V4-Pro — 复杂推理（多跳影响分析）
response = litellm.completion(
    model="deepseek/deepseek-v4-pro",        # V4-Pro
    messages=[...],
    thinking={"type": "enabled", "budget_tokens": 8192},
)
```

> 📌 **为什么用 litellm？**
> 如果 DeepSeek 不可用或需要对比效果，一行配置切换：
> ```python
> model="openai/gpt-4o"       # 切换到 GPT-4o
> model="anthropic/claude-3"  # 切换到 Claude
> ```

---

## 十、成本控制

| 策略 | 说明 |
|------|------|
| **V4-Flash 为主力** | 90%+ 任务用 V4-Flash ($0.14/$0.28)，仅复杂推理用 V4-Pro |
| **Prompt 缓存** | 固定 system prompt 命中缓存后输入价降 80-92% |
| **规则优先** | Impact Engine 优先规则，LLM 只补充复杂推理 |
| **事件去重** | 同一事件多篇报道只触发一次 Impact Engine，大幅减少推理调用 |
| **去重** | content_hash 去重，不重复抽取 |
| **增量处理** | 每日只处理新增文档 |
| **结果缓存** | 抽取结果存 phoenixA，相同内容不重复调 LLM |
| **Prompt 版本控制** | 新旧 prompt 结果共存，避免全量重跑 |
| **数据源分类** | 图谱构建型文档低频处理，不每日全量 |

**月度预估**（稳态，V4-Flash 为主 + Prompt 缓存）：

| 任务 | 模型 | 日均 tokens | 月 tokens | 月成本（含缓存） |
|------|------|------------|-----------|----------------|
| 新闻过滤（~100 篇/天） | V4-Flash | ~200K in + 50K out | ~7.5M | ~$0.5 |
| 文档抽取（~20 篇/天） | V4-Flash(High) | ~500K in + 200K out | ~21M | ~$2 |
| 事件解析+去重（~10 事件/天） | V4-Flash | ~100K in + 50K out | ~4.5M | ~$0.3 |
| 影响推理（~5 新事件/天） | **V4-Pro**(High) | ~200K in + 100K out | ~9M | ~$5 |
| 公司综述（按需） | V4-Flash | — | ~3M | ~$0.3 |
| **月度总计** | | | **~45M** | **~$8-10** |

> 对比 GPT-4o 同等用量：~$200-300/月 → DeepSeek V4-Flash 节省 **97%+**。
> V4-Flash + Prompt 缓存是成本杀手级组合。

---

## 十一、实施路线

> 分为**第一期**（跑通核心链路）和**第二期**（增强优化），避免一次做太多。

### 🥇 第一期 Phase 1：数据通路 + 手动数据源（2-3 周）

```
目标：手动上传文档 → skill 抽取 → JSON → PostgreSQL → 基础图谱
数据源策略：种子数据手动收集上传，不做自动采集

交付物：
  ✅ phoenixA 新增 pg 数据源 + kg.* 表（含 events 表）+ CRUD API
  ✅ MinIO atlas-documents bucket（多目录）
  ✅ atlas 文档上传 API → MinIO + phoenixA(documents)
  ✅ PDF/HTML 解析 + 切分
  ✅ LLM 抽取（DeepSeek + skill v5）+ Pydantic 校验
  ✅ 抽取结果存 phoenixA(extractions)
  ✅ Graph Builder → Neo4j
  ✅ 事件指纹去重逻辑（Layer 1 + Layer 2）
  ✅ 分类配置化（atlas.yaml 管理所有枚举）
  ✅ LLM 抽取全部 19 种关系 + OTHER 兜底
  ✅ 30-50 篇种子文档跑通（手动收集，含研报 + 新闻 + 公告）
  ✅ Neo4j Browser 验证图谱质量
```

### 🥈 第一期 Phase 2：影响引擎（2 周）

```
目标：事件 → 受影响公司（规则版 v1）

交付物：
  ✅ 事件解析（LLM → 结构化影响对象）
  ✅ 图谱传播（BFS 1-3 层）
  ✅ 影响计算（规则引擎 v1）
  ✅ 影响日志持久化
  ✅ 公司综述生成
  ✅ API: event→impact, company→review
```

### 🥉 第一期 Phase 3：每日运行 + 基础前端（2-3 周）

```
目标：跑通每日 pipeline + 基础可视化

交付物：
  ✅ RSS 新闻源对接（免费源）
  ✅ 每日 pipeline（含事件去重）
  ✅ cronjob 定时触发
  ✅ 每日洞察报告（去重后的新事件列表）
  ✅ cthulhu 基础 knowledge-graph 页面
  ✅ 图谱可视化 + 事件影响 + 公司综述页面
```

### 第二期（第一期稳定运行后）：增强 + 自动化 + 闭环

```
目标：数据源自动化 + 分类调优 + 回溯验证

交付物：
  ☐ 研报/行业分析自动化采集
  ☐ 多跳传播 + distance decay 优化
  ☐ 关系类型/事件类型 `OTHER` 审计 → 识别高频模式 → 拆分新类型
  ☐ 事件去重 Layer 3（语义相似度兜底）
  ☐ 事件类型 `other` 审计 + 分类拆分
  ☐ 公司标准化扩展到港股/美股
  ☐ 影响预测 vs 实际股价对比（回溯验证）
  ☐ 影响叠加分析
```

---

## 十二、项目结构

```
app/projects/atlas/
├── atlas/
│   ├── main.py                     # 入口
│   ├── api/
│   │   ├── routes.py               # App + 路由注册
│   │   ├── documents.py            # 文档上传/管理
│   │   ├── web_clip.py             # 浏览器 bookmarklet 提交入口
│   │   ├── extraction.py           # 抽取触发/查询
│   │   ├── reasoning.py            # 影响分析/公司综述
│   │   ├── graph.py                # 图谱查询
│   │   └── pipeline.py             # 每日流水线
│   ├── connectors/
│   │   ├── neo4j_client.py         # Neo4j 驱动（直连）
│   │   ├── llm_client.py           # LLM 统一调用（litellm → V4-Flash/V4-Pro）
│   │   ├── phoenixa_client.py      # phoenixA HTTP 客户端
│   │   ├── minio_client.py         # MinIO S3 客户端
│   │   └── news_fetcher.py         # 新闻/政策/公告拉取
│   ├── core/
│   │   └── config.py
│   ├── models/
│   │   ├── graph_schema.py         # 抽取输出 schema（对应 skill v5）
│   │   ├── document.py             # 文档/任务元数据
│   │   ├── event.py                # 事件模型（指纹/去重/类型枚举）
│   │   └── impact.py               # 影响分析输出模型
│   └── services/
│       ├── ingestion.py            # 文档解析+切分 → MinIO + phoenixA
│       ├── llm_extractor.py        # LLM 抽取+校验 → phoenixA(extractions)
│       ├── graph_builder.py        # ⭐ 图谱构建器 → Neo4j
│       ├── graph_query.py          # 图谱查询（只读）
│       ├── event_dedup.py          # ⭐ 事件去重（指纹生成+匹配）
│       ├── impact_engine.py        # ⭐ 影响引擎
│       ├── impact_rules.py         # ⭐ 规则引擎
│       ├── company_review.py       # 公司综述生成
│       └── daily_pipeline.py       # 每日流水线编排
├── config/
│   └── atlas.yaml
├── docs/
│   └── (本文档)
├── pyproject.toml
└── README.md
```

---

## 十三、数据源获取方案（低成本策略）

> 约束：经费有限，不买昂贵的 Wind/Choice 终端。优先免费 → 低成本 → 半自动 → 手动。

### 13.1 第一期种子数据（手动收集 → MinIO）

> 目标：收集 30-50 篇高质量文档，跑通全流程，验证图谱质量。不求量，求覆盖面。

| 数据类型 | 获取方式 | 数量 | 说明 |
|---------|---------|------|------|
| **行业研报** | 闲鱼/多多购买研报合集 | 10-15 篇 | 选 3-5 个重点行业（锂电/半导体/光伏/AI/医药） |
| **财报** | 巨潮资讯网免费下载 | 5-10 篇 | 重点公司年报（5K 只里选核心 20-30 家） |
| **行业分析** | 免费白皮书/行业报告网站 | 5 篇 | 产业链全景图类 |
| **新闻/政策** | 手动复制粘贴 | 10-20 篇 | 近期热点新闻 + 重要政策 |

**上传方式**：通过 Atlas 文档上传 API 或直接传 MinIO

### 13.2 免费/低成本数据源（第一期 Phase 3 开始接入）

#### 📰 新闻（每日事件触发）

| 来源 | 方式 | 成本 | 可靠性 | 说明 |
|------|------|------|--------|------|
| **新浪财经 RSS** | RSS 订阅 | 免费 | ⭐⭐⭐ | `https://finance.sina.com.cn/rss/` |
| **东方财富要闻** | RSS / 页面抓取 | 免费 | ⭐⭐⭐ | 财经新闻最全 |
| **证券时报** | RSS | 免费 | ⭐⭐⭐⭐ | 官方媒体，政策类新闻 |
| **Google News RSS** | RSS（需代理） | 免费 | ⭐⭐⭐ | 全球新闻，英文为主 |
| **CLS 财联社** | 页面抓取 | 免费 | ⭐⭐⭐⭐ | 快讯/电报类，短文本 |

> RSS 是最稳定的免费新闻源：不需要登录、不会被封、格式标准。
> 建议第一期先接入 3-5 个 RSS 源，用 `feedparser` 库解析。

#### 📋 公告

| 来源 | 方式 | 成本 | 说明 |
|------|------|------|------|
| **巨潮资讯网** | 页面抓取 / API | 免费 | A 股上市公司全部公告 |
| **上交所/深交所公告** | 页面抓取 | 免费 | 官方一手数据 |

#### 📜 政策

| 来源 | 方式 | 成本 | 说明 |
|------|------|------|------|
| **国务院/发改委/工信部** | RSS / 页面抓取 | 免费 | 政策文件，更新频率低 |
| **商务部** | 页面抓取 | 免费 | 关税/贸易政策 |

#### 📊 研报（低成本方案）

| 来源 | 方式 | 成本 | 说明 |
|------|------|------|------|
| **闲鱼研报合集** | 一次性购买 | ¥10-50 | 买某行业/时段的研报 PDF 打包 |
| **慧博投研资讯** | 免费注册 + 每日限量 | 免费 | 每天可下几篇，够用 |
| **发现报告** | 免费/低价会员 | ~¥100/年 | 行业报告聚合平台 |
| **萝卜投研** | 部分免费 | 免费 | 研报摘要 |

### 13.3 半自动采集方案：浏览器辅助上传

> 对于不好自动爬取的网站（反爬严格、需登录），用**浏览器扩展 + 手动触发**方案。

```
方案：Browser Bookmarklet / 简单浏览器扩展

流程：
  1. 用户正常浏览网页（看研报/新闻/政策）
  2. 看到有价值的内容 → 点击 bookmarklet
  3. Bookmarklet 抓取当前页面内容（title + body text + URL）
  4. POST 到 Atlas 文档上传 API
  5. Atlas 自动：存 MinIO → phoenixA(documents) → 排队待抽取

技术实现（简单 JS bookmarklet）：
  javascript:(function(){
    var data = {
      title: document.title,
      url: window.location.href,
      content: document.body.innerText.substring(0, 50000),
      doc_type: prompt("类型: news/research/policy/announcement", "news")
    };
    fetch("https://atlas.your-domain/api/v1/ingest/web-clip", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    }).then(r => alert("✅ 已提交 Atlas"));
  })();

优点：
  ✅ 零成本
  ✅ 不会被封（用户手动浏览，不是爬虫）
  ✅ 人工质量筛选（只提交有价值的文档）
  ✅ 覆盖任何网站

缺点：
  ❌ 依赖人工操作（不自动）
  ❌ 需要养成习惯
```

### 13.4 爬虫策略（谨慎使用）

> 原则：**爬虫只用于公开数据 + 低频率 + 有 robots.txt 允许的来源**。

| 方案 | 说明 | 风险 |
|------|------|------|
| **RSS Parser** | `feedparser` 库，标准协议 | ✅ 无风险 |
| **巨潮资讯网** | 公告数据，频率每天 1 次 | ⚠️ 低风险（公开数据） |
| **政府网站** | 政策文件，频率每周 1 次 | ✅ 公开信息 |
| **商业网站（东财/雪球等）** | 不建议爬取 | ❌ 高风险封号 → 用 RSS/bookmarklet 替代 |

```
爬虫代码放 tools/py/crawler/，atlas 通过 HTTP 调用
频率控制：
  └── RSS: 每日 2-4 次
  └── 公告: 每日 1 次
  └── 政策: 每周 1 次
  └── 加随机延迟 + User-Agent 轮换
```

### 13.5 数据源获取路线

```
第一期 Phase 1（手动）：
  → 闲鱼买研报 + 巨潮下载财报 + 手动复制新闻
  → 全部通过 Atlas 上传 API → MinIO
  → 30-50 篇种子数据

第一期 Phase 3（半自动）：
  → 接入 3-5 个 RSS 新闻源（自动拉取）
  → Bookmarklet（阅读时一键提交）
  → 巨潮公告爬虫（每日 1 次）

第二期（自动化）：
  → 研报自动抓取（慧博/发现报告）
  → 政策网站定期爬取
  → 更多 RSS 源
  → 可能的低成本 API 接入
```

---

## 十四、已决策事项

| # | 事项 | 决策 | 理由 | 日期 |
|---|------|------|------|------|
| 1 | **公司标准化** | 第一期只支持 A 股，使用 phoenixA `security_registry` | 港股/美股第二期逐步引入 | 2026-05-07 |
| 2 | **前端可视化** | 在 cthulhu (Angular) 中集成，AntV G6 或 ECharts 均可 | 都有 Angular 集成方案，实现时选 | 2026-05-07 |
| 3 | **回溯验证** | 放到第二期 | 第一期先确保图谱和产业分析质量成熟 | 2026-05-07 |
| 4 | **事件去重调优** | 第一期用固定时间桶，第二期再调优 | 先跑起来，积累数据后用数据驱动调优 | 2026-05-07 |
| 5 | **语义去重(Layer 3)** | 放到第二期 | fingerprint 主去重够用，语义兜底是优化 | 2026-05-07 |
| 6 | **研报数据源** | 第一期手动收集+闲鱼购买，第二期考虑自动化 | 先跑通流程，稳定后再自动化 | 2026-05-07 |
| 7 | **关系类型** | LLM 全量抽取 19 种 + OTHER 兜底，不做 core/extended 分级 | 充分利用已知类型，OTHER 第二期审计 | 2026-05-07 |
| 8 | **分类治理** | 配置驱动 + other 兜底 + 定期审计 | 分类可演进，不一次定死 | 2026-05-07 |

---

## 十五、项目启动前置清单（非代码工作）

> 除了写代码之外，需要做完以下事情才能让 Atlas 顺利运行。
> 按优先级排序，标注了当前状态和预估工时。

### 15.1 基础设施准备

| # | 任务 | 当前状态 | 需要做什么 | 预估工时 | 阶段 |
|---|------|---------|-----------|---------|------|
| 1 | **Neo4j 配置调优** | ✅ 已 Docker 部署，未调参 | 见下方 15.2 | 1-2 小时 | Phase 1 |
| 2 | **PostgreSQL 安装 + kg schema** | ❓ 待确认 VM2 是否已装 PG | 按 INFRA 文档 Phase A 执行：安装 PG16 → 创建 chaos_db → 建 kg schema + 表 | 2-4 小时 | Phase 1 |
| 3 | **MinIO atlas-documents bucket** | ✅ MinIO 已运行 | 创建 bucket + 子目录结构（earnings/research/news/...） | 10 分钟 | Phase 1 |
| 4 | **DeepSeek API Key** | ❓ 待注册 | 注册 [platform.deepseek.com](https://platform.deepseek.com) → 充值 → 获取 API Key | 15 分钟 | Phase 1 |
| 5 | **Docker Compose 更新** | 需更新 | 在 `deploy/docker/docker-compose/` 新增 atlas.yaml，配置 atlas 容器 + 网络 | 30 分钟 | Phase 1 |
| 6 | **Dockerfile-atlas** | 需创建 | 在 `deploy/docker/dockerfile/` 创建，基于 Python 3.11 + 依赖 | 30 分钟 | Phase 1 |

### 15.2 Neo4j 配置调优（详细）

> Neo4j 已在 Docker 中运行，但默认配置性能差。需要调以下参数：

```bash
# ── 在 Neo4j Docker Compose 或 neo4j.conf 中调整 ────────────

# 内存（根据 INFRA 文档分配 6-8 GB 给 Neo4j）
NEO4J_server_memory_heap_initial__size=3g
NEO4J_server_memory_heap_max__size=3g
NEO4J_server_memory_pagecache_size=3g

# APOC 插件（图谱操作需要）
NEO4J_PLUGINS=["apoc"]

# 允许从 atlas 容器访问
NEO4J_dbms_default__listen__address=0.0.0.0

# Bolt 协议端口（atlas 用这个连接）
# ports: 7687:7687（Bolt）, 7474:7474（Browser）

# 数据持久化（必须挂载卷）
# volumes: neo4j-data:/data, neo4j-logs:/logs
```

```
需要确认/操作的事项：
  □ 当前 Neo4j 容器分配了多少内存？→ 调整到 6-8 GB
  □ 数据目录是否挂载到 512GB NVMe？→ 确保不在容器内临时存储
  □ APOC 插件是否已安装？→ atlas 的 Cypher 查询会用到
  □ Neo4j Browser 能否正常访问（http://VM1_IP:7474）？
  □ 创建 atlas 专用数据库用户（不用 neo4j/neo4j 默认密码）
```

### 15.3 phoenixA 改动

| # | 任务 | 说明 | 预估工时 |
|---|------|------|---------|
| 1 | **新增 PostgreSQL 数据源** | phoenixA 当前连 MySQL，需新增 PG 连接（可并行存在） | 1-2 天 |
| 2 | **新增 kg schema CRUD** | documents / extractions / events / impact_logs / daily_runs / graph_ingestions 的 API | 3-5 天 |
| 3 | **kg schema 数据库迁移文件** | `migrations/` 目录下新增 kg 表的 DDL | 1 天 |

### 15.4 数据准备

| # | 任务 | 说明 | 预估工时 | 阶段 |
|---|------|------|---------|------|
| 1 | **种子数据收集** | 手动收集 30-50 篇文档（研报+新闻+财报+公告） | 3-5 小时 | Phase 1 |
| 2 | **闲鱼购买研报** | 选 3-5 个行业的研报 PDF 合集 | ¥10-50 + 1 小时 | Phase 1 |
| 3 | **巨潮下载财报** | 选 20-30 家核心公司的最新年报 | 1-2 小时 | Phase 1 |
| 4 | **新闻样本整理** | 近期 10-20 条产业链相关新闻 | 1 小时 | Phase 1 |
| 5 | **RSS 源整理** | 确定 3-5 个可用的财经 RSS 地址，测试 feedparser 解析 | 1 小时 | Phase 3 |

### 15.5 账号与配置

| # | 任务 | 说明 | 阶段 |
|---|------|------|------|
| 1 | **DeepSeek 账号注册 + 充值** | 充 ¥50 够用几个月 | Phase 1 |
| 2 | **atlas.yaml 配置文件** | DeepSeek API Key、Neo4j 连接、phoenixA URL、MinIO 连接 | Phase 1 |
| 3 | **Neo4j 用户创建** | 创建 atlas 专用用户，不用默认 neo4j | Phase 1 |
| 4 | **MinIO 访问凭证** | 确认 atlas 可用的 access_key / secret_key | Phase 1 |

### 15.6 完整启动前 Checklist

```
── 基础设施（开始写代码前必须完成）─────────────────────────

□ VM2: PostgreSQL 16 已安装并运行
□ VM2: chaos_db 数据库已创建，kg schema 已建
□ VM2: PG 网络配置允许 VM1 连接（pg_hba.conf）
□ VM1: Neo4j Docker 内存调到 6-8GB
□ VM1: Neo4j 数据卷挂载到 NVMe
□ VM1: Neo4j APOC 插件已安装
□ VM1: Neo4j 创建 atlas 专用用户
□ VM1: MinIO atlas-documents bucket 已创建
□ VM1: MinIO 子目录结构已建（earnings/research/news/...）

── 账号与密钥 ──────────────────────────────────────────

□ DeepSeek 账号注册完成
□ DeepSeek API Key 已获取
□ DeepSeek 余额 ≥ ¥50
□ MinIO access_key/secret_key 确认可用

── 配置文件 ────────────────────────────────────────────

□ config/atlas.yaml 已写好（所有连接信息 + 分类枚举）
□ deploy/docker/dockerfile/Dockerfile-atlas 已创建
□ deploy/docker/docker-compose/atlas.yaml 已创建
□ atlas 容器与 neo4j 在同一 Docker 网络

── phoenixA 改动 ──────────────────────────────────────

□ phoenixA 新增 PG 数据源配置
□ kg schema 迁移文件完成
□ kg.* 表 CRUD API 开发完成
□ phoenixA 重新部署并验证 kg API 可用

── 数据准备 ────────────────────────────────────────────

□ 种子文档收集完成（30-50 篇）
□ 文档已按类型分好（研报/财报/新闻/公告）
□ 文档已上传到 MinIO atlas-documents bucket

── 验证 ──────────────────────────────────────────────

□ atlas 容器启动成功，健康检查通过
□ atlas → Neo4j 连接正常（Bolt 协议）
□ atlas → phoenixA API 调用正常
□ atlas → MinIO 读写正常
□ atlas → DeepSeek API 调用正常（测试一次 completion）
□ 手动上传 1 篇文档 → 全流程跑通 → Neo4j Browser 验证
```

---

## 十六、待决策事项

1. **种子数据行业选择**：第一期重点覆盖哪 3-5 个行业？（建议：锂电池/新能源、半导体/AI、光伏、医药）
2. **图可视化库最终选型**：AntV G6 vs ECharts graph，在 cthulhu 中做技术验证后决定
3. **Atlas 部署域名/端口**：Docker Compose 中 atlas 的端口分配

---

## 附录：Atlas 设计决策记录

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| 1 | 抽取结果存 PostgreSQL 而非直接写 Neo4j | 可回溯+可重跑+可调 prompt | 2026-04-29 |
| 2 | Impact Engine 规则+LLM 混合 | 规则可预测/低成本/可调试 | 2026-04-29 |
| 3 | Graph Builder 独立于 LLM Extractor | 质量门控：低 confidence 不入图 | 2026-04-29 |
| 4 | 影响强度用公式而非纯 LLM | 可量化/可回溯/可优化 | 2026-04-29 |
| 5 | 单进程三逻辑模块，非微服务 | 个人开发者，避免运维复杂度 | 2026-04-29 |
| 6 | Neo4j 只存精简数据 | 图谱精简高效，详情在 PostgreSQL | 2026-04-29 |
| 7 | 结构化数据通过 phoenixA API 访问 | 复用数据中台 | 2026-04-29 |
| 8 | 原始文档存 MinIO | 已有基础设施 | 2026-04-29 |
| 9 | 数据源分两类：图谱构建型 + 事件触发型 | 不同数据源作用不同，处理策略不同 | 2026-05-07 |
| 10 | 事件去重用指纹为主（不用 embedding） | 零成本+确定性+可解释，语义兜底留第二期 | 2026-05-07 |
| 11 | LLM 用 DeepSeek V4-Flash(主力) + V4-Pro(复杂推理) | Flash 性价比极高($0.14/$0.28)，Pro 仅复杂推理用 | 2026-05-07 |
| 12 | kg.events 表做规范化事件存储 | 事件去重 + 热度追踪 + 影响关联 | 2026-05-07 |
| 13 | 分类配置化 + other 兜底 + 渐进拆分 | 分类可演进，不一次定死 | 2026-05-07 |
| 14 | 关系类型全量抽取 + OTHER 兜底 | LLM 应充分利用已知类型，不应人为限制；OTHER 后续审计拆分 | 2026-05-07 |
| 15 | 第一期数据源：手动收集+闲鱼+RSS | 经费有限，先跑通再自动化 | 2026-05-07 |
| 16 | Bookmarklet 半自动采集 | 零成本+不会被封+人工质量筛选 | 2026-05-07 |
| 17 | 回溯验证/语义去重/去重调优放第二期 | 第一期聚焦核心链路 | 2026-05-07 |
| 18 | 公司标准化第一期只支持 A 股 | 港股/美股第二期逐步引入 | 2026-05-07 |

