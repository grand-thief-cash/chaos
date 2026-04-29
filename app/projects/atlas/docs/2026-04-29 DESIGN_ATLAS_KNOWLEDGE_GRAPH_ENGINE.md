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

**要求**：任意输入一个公司名，自动聚合图谱数据 + LLM 生成综述。

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

## 三、数据层设计

### 设计原则

> ❗ 抽取结果必须先持久化到 PostgreSQL（通过 phoenixA），再通过 Graph Builder 写入图谱。
>
> 原因：**可回溯 + 可重跑 + 可调 prompt**。

### 3.1 数据访问策略

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
  │───→ LLM API（GPT-4o / 4o-mini）
```

| 数据 | 走 phoenixA | 原因 |
|------|------------|------|
| documents / extractions / impact_logs | ✅ | 结构化元数据，复用数据中台 |
| daily_runs | ✅ | 运行日志 |
| Neo4j 图谱 | ❌ 直连 | Cypher 查询太领域化，不适合通用 API |
| MinIO 文件 | ❌ 直连 | S3 协议直连 |

**对 phoenixA 的影响**：新增 `kg` 数据域，与 `bars` / `reference` / `taxonomy` 并列。

### 3.2 原始文档存储 → MinIO

```
MinIO
├── atlas-documents/         ← atlas 专用 bucket
│   ├── earnings/            # 财报 PDF
│   ├── research/            # 研报 PDF
│   ├── news/                # 新闻文本
│   └── announcements/       # 公告
```

- S3 协议直连（`boto3` / `minio-py`）
- `documents` 表只存 `file_path`（MinIO 对象路径），不存文件本身

### 3.3 PostgreSQL 表设计（kg schema）

```sql
-- ① 文档元数据
CREATE TABLE kg.documents (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       VARCHAR(64) UNIQUE NOT NULL,
    title        VARCHAR(512),
    doc_type     VARCHAR(32) NOT NULL,            -- earnings|research|news|announcement
    company      VARCHAR(128),
    publish_time TIMESTAMP,
    file_path    VARCHAR(1024),                    -- MinIO 对象路径
    content_hash VARCHAR(64),                      -- 去重
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

-- ③ 图谱写入记录
CREATE TABLE kg.graph_ingestions (
    id              BIGSERIAL PRIMARY KEY,
    extraction_id   BIGINT REFERENCES kg.extractions(id),
    nodes_created   INT DEFAULT 0,
    edges_created   INT DEFAULT 0,
    nodes_merged    INT DEFAULT 0,
    ingested_at     TIMESTAMP DEFAULT NOW()
);

-- ④ 每日流水线记录
CREATE TABLE kg.daily_runs (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    news_fetched     INT DEFAULT 0,
    news_relevant    INT DEFAULT 0,
    extractions_ok   INT DEFAULT 0,
    extractions_fail INT DEFAULT 0,
    impacts_generated INT DEFAULT 0,
    total_cost_usd   DECIMAL(10,4),
    status           VARCHAR(16),
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP
);

-- ⑤ 影响日志（推理结果持久化）
CREATE TABLE kg.impact_logs (
    id            BIGSERIAL PRIMARY KEY,
    event_name    VARCHAR(512),
    event_time    VARCHAR(32),
    source_doc_id VARCHAR(64),
    impact_json   JSONB NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);
```

### 3.4 phoenixA 需要新增的 API

```
POST   /api/v1/kg/documents                  # 创建文档记录
GET    /api/v1/kg/documents                  # 列表查询
GET    /api/v1/kg/documents/{doc_id}         # 查询单个
PUT    /api/v1/kg/documents/{doc_id}         # 更新状态

POST   /api/v1/kg/extractions                # 存储抽取结果
GET    /api/v1/kg/extractions                # 按 doc_id/prompt_version 查询
GET    /api/v1/kg/extractions/{id}           # 单条详情

POST   /api/v1/kg/graph-ingestions           # 记录入图操作
POST   /api/v1/kg/daily-runs                 # 记录每日运行
GET    /api/v1/kg/daily-runs                 # 查看历史

POST   /api/v1/kg/impact-logs                # 存储影响分析结果
GET    /api/v1/kg/impact-logs                # 按事件/时间查询
```

---

## 四、图谱层设计

### 4.1 Graph Builder

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

### 4.2 Neo4j 存储策略

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

### 4.3 节点模型

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

### 4.4 关系类型（19 种）

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

## 五、推理层 — Impact Engine

> 系统的 Alpha 核心。图谱人人能建，影响判断的准确性和速度决定投资价值。

### 5.1 三步推理法

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

### 5.2 规则引擎 vs LLM 的分工

| 场景 | 方法 | 理由 |
|------|------|------|
| 资源价格变动 | **规则** | 逻辑清晰、可预测 |
| 供给紧张/过剩 | **规则** | 方向确定 |
| 关税/贸易政策 | **规则 + LLM** | 规则定方向，LLM 补路径 |
| 技术突破/并购 | **LLM** | 影响复杂，需要推理 |
| 宏观政策（加息/降息） | **规则 + LLM** | 传导路径多元 |
| 突发事件（事故/灾害） | **LLM** | 需要上下文理解 |

### 5.3 影响强度评分

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

### 5.4 影响输出持久化

每次推理结果存到 `kg.impact_logs`（通过 phoenixA API），用于：
1. 回溯验证（事后看是否判断正确）
2. 趋势分析（同一公司历史受影响次数/方向）
3. 模型迭代（用历史结果调优规则）

---

## 六、服务设计

### 6.1 Atlas 作为独立服务，不拆分

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

### 6.2 Atlas 内部模块

```
atlas (一个 FastAPI 进程)
│
├── Ingestion 模块
│   ├── 文档上传 → MinIO + phoenixA(documents)
│   ├── PDF/HTML 解析 + 切分
│   └── 新闻拉取
│
├── Extraction 模块
│   ├── LLM 调用 (skill v5)
│   ├── Pydantic 校验
│   ├── 结果存 phoenixA(extractions)
│   └── Graph Builder → Neo4j
│
└── Reasoning 模块 ← 核心
    ├── 事件解析 (LLM)
    ├── 图谱传播 (Neo4j BFS)
    ├── 影响计算 (规则 + LLM)
    ├── 公司综述 (聚合 + LLM)
    └── 结果存 phoenixA(impact_logs)
```

---

## 七、计算触发机制

### 7.1 两种模式

```
模式 A：事件驱动（实时性）
  新文档上传 → 抽取 → 存 phoenixA → Graph Builder → Neo4j
  → [若含事件/政策] → 自动触发 Impact Engine

模式 B：每日批处理（稳定性，主模式）
  Cron 08:00 触发：
    1. 拉取昨日~今晨新闻
    2. 过滤（GPT-4o-mini）
    3. 抽取（GPT-4o + skill v5）
    4. 存 phoenixA(extractions)
    5. Graph Builder → Neo4j
    6. 聚合新事件
    7. Impact Engine（规则+LLM）
    8. 输出「今日影响清单」
    9. 存 phoenixA(impact_logs)
```

### 7.2 流水线编排

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Fetch News │───→│  Filter     │───→│  Extract     │───→│  phoenixA    │
│  (RSS/API)  │    │ (4o-mini)   │    │  (4o + skill)│    │ (extractions)│
└─────────────┘    └─────────────┘    └──────────────┘    └──────┬───────┘
                                                                  │
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────▼───────┐
│ phoenixA    │←───│ Impact Calc  │←───│ Event Parse  │←───│Graph Builder │
│(impact_logs)│    │ (规则+LLM)   │    │ + Graph BFS  │    │ → Neo4j      │
└──────┬──────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │
┌──────▼──────┐
│ 今日洞察报告 │
└─────────────┘
```

---

## 八、技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 服务框架 | **FastAPI** (Python) | 异步、与 artemis 同栈 |
| 元数据存储 | **PostgreSQL JSONB** (通过 phoenixA) | 可回溯、JSONB 查询 |
| 图数据库 | **Neo4j Community 5.x** (直连) | 免费、Cypher 直观 |
| 文件存储 | **MinIO** (S3 协议) | 已有基础设施 |
| LLM | **litellm** → GPT-4o + 4o-mini | 统一接口、分层模型 |
| 文档解析 | **PyMuPDF + BeautifulSoup** | 轻量 |
| 定时调度 | **cronjob** (已有 Go 服务) | 不新增组件 |

---

## 九、成本控制

| 策略 | 说明 |
|------|------|
| **分层模型** | 过滤用 4o-mini ($0.15/1M)，抽取用 4o ($2.5/1M) |
| **规则优先** | Impact Engine 优先规则，LLM 只补充复杂推理 |
| **去重** | content_hash 去重，不重复抽取 |
| **增量处理** | 每日只处理新增新闻 |
| **结果缓存** | 抽取结果存 phoenixA，相同内容不重复调 LLM |
| **Prompt 版本控制** | 新旧 prompt 结果共存，避免全量重跑 |

**月度预估**（稳态）：~$15-20

---

## 十、实施路线

### 🥇 Phase 1：数据通路（2-3 周）— 不做推理

```
目标：文档 → skill 抽取 → JSON → PostgreSQL → 基础图谱

交付物：
  ✅ phoenixA 新增 pg 数据源 + kg.* 表 + CRUD API
  ✅ MinIO atlas-documents bucket
  ✅ 文档上传 → MinIO + phoenixA(documents)
  ✅ PDF/HTML 解析 + 切分
  ✅ LLM 抽取（skill v5）+ Pydantic 校验
  ✅ 抽取结果存 phoenixA(extractions)
  ✅ Graph Builder → Neo4j
  ✅ 10-20 篇种子文档跑通全流程
  ✅ Neo4j Browser 验证
```

### 🥈 Phase 2：影响引擎（2 周）— 核心价值

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

### 🥉 Phase 3：每日运行 + 增强（2 周）

```
目标：自动化 + 多跳传播 + 强度评分

交付物：
  ✅ 新闻数据源对接
  ✅ 每日 pipeline
  ✅ cronjob 定时触发
  ✅ 多跳传播 + distance decay
  ✅ 每日洞察报告
  ✅ 影响叠加分析
```

### Phase 4：前端 + 闭环（2 周）

```
目标：可视化 + 回溯验证

交付物：
  ✅ cthulhu knowledge-graph feature
  ✅ AntV G6 图可视化
  ✅ 事件影响 / 公司综述 / 每日洞察页面
  ✅ 影响预测 vs 实际股价对比
```

---

## 十一、项目结构

```
app/projects/atlas/
├── atlas/
│   ├── main.py                     # 入口
│   ├── api/
│   │   ├── routes.py               # App + 路由注册
│   │   ├── documents.py            # 文档上传/管理
│   │   ├── extraction.py           # 抽取触发/查询
│   │   ├── reasoning.py            # 影响分析/公司综述
│   │   ├── graph.py                # 图谱查询
│   │   └── pipeline.py             # 每日流水线
│   ├── connectors/
│   │   ├── neo4j_client.py         # Neo4j 驱动（直连）
│   │   ├── llm_client.py           # LLM 统一调用
│   │   ├── phoenixa_client.py      # phoenixA HTTP 客户端
│   │   ├── minio_client.py         # MinIO S3 客户端
│   │   └── news_fetcher.py         # 新闻拉取
│   ├── core/
│   │   └── config.py
│   ├── models/
│   │   ├── graph_schema.py         # 抽取输出 schema（对应 skill v5）
│   │   ├── document.py             # 文档/任务元数据
│   │   └── impact.py               # 影响分析输出模型
│   └── services/
│       ├── ingestion.py            # 文档解析+切分 → MinIO + phoenixA
│       ├── llm_extractor.py        # LLM 抽取+校验 → phoenixA(extractions)
│       ├── graph_builder.py        # ⭐ 图谱构建器 → Neo4j
│       ├── graph_query.py          # 图谱查询（只读）
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

## 十二、待决策事项

1. **新闻数据源**：对接哪些 RSS/API？是否扩展 `tools/py/crawler`？
2. **公司标准化对照表**：从 phoenixA 的 `security_registry` 拉取
3. **前端图可视化**：AntV G6 还是 ECharts graph？
4. **回溯验证**：影响预测 vs 次日股价涨跌对比机制

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

