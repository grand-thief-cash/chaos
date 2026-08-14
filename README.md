





# Chaos 金融量化研究平台

> 自建的金融量化研究与数据治理平台。覆盖多源行情采集、财务与研报数据治理、研报知识图谱、特征平台、信号研究与回测全链路，统一前端可视化，全栈自研并自托管于单台物理服务器。
>

---

## 目录

- [项目定位](#项目定位)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [各服务说明](#各服务说明)
- [数据源](#数据源)
- [基础设施与部署](#基础设施与部署)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [文档导航](#文档导航)
- [开发与测试](#开发与测试)
- [版本与路线图](#版本与路线图)

---

## 项目定位

Chaos 是一个面向量化研究的语义、计算与物化基础设施平台，而非单一策略或单一应用。它要持续回答几个问题：

1. 系统中有哪些可用的数据与特征？每个的业务含义、值类型、适用实体、版本是什么？
2. 特征由什么实现（Python / 表达式 / 供应商 / 模型 / 外部服务），依赖哪些原始字段或其他特征？
3. 一次计算使用了哪个版本、哪个数据截止时间、哪些证券，结果是否持久化、可追溯、可复现？
4. 研报中的产业链关系、事件影响如何结构化为知识图谱，并在不破坏平台边界的前提下被消费？
5. 数据不足或模型超出适用范围时，系统能否明确输出降级结论，而不是伪造安全结论？

平台统一的是命名、定义、版本、实现方式、依赖关系、运行上下文、血缘治理与查询协议，**不强制所有数据采用相同的物理模型**。

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           cthulhu (Angular 17)                           │
│                前端：行情 / 图谱 / 回测 / 信号 / 洞察 / 风险              │
└─────────┬────────────────┬────────────────┬────────────────┬────────────┘
          │                │                │                │
┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
│   phoenixA     │ │   artemis    │ │    atlas     │ │   cronjob    │
│   (Go)         │ │   (Python)   │ │   (Python)   │ │   (Go)       │
│   数据中台      │ │   行情拉取    │ │  知识图谱     │ │   调度中心    │
│   金融数据治理  │ │   回测/特征   │ │  LLM 抽取     │ │   定时任务    │
└───────┬────────┘ └──────────────┘ └──────┬───────┘ └──────────────┘
        │                                  │
        │              ┌───────────────────┘
        │              │
┌───────▼──────────────▼───────────────────────────────────────────────┐
│                    基础设施层                                         │
│  ┌──────────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ PostgreSQL 16    │  │ Neo4j    │  │ MinIO    │  │ LLM API  │     │
│  │ + TimescaleDB    │  │ (图谱)   │  │ (2.7TB)  │  │ NIM/OR/  │     │
│  │ + PGVector       │  │          │  │          │  │ 智谱/Ollama│     │
│  └──────────────────┘  └──────────┘  └──────────┘  └──────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

**服务交互**：

- `cronjob ──HTTP──> atlas / artemis / phoenixA`：定时触发各服务的周期 pipeline。
- `atlas ──HTTP──> phoenixA`：结构化数据 CRUD（所有持久化收口到 phoenixA）。
- `atlas ──S3──> MinIO`：研报 PDF 上传/下载；`atlas ──Bolt──> Neo4j`：图谱读写；`atlas ──HTTP──> LLM API`：抽取与归纳。
- `cthulhu ──HTTP──> atlas / phoenixA`：查询、分析、洞察与基础数据。
- `artemis ──HTTP──> phoenixA`：行情落库；`artemis ──HTTP──> atlas`（可选）：查产业链辅助策略。

---

## 技术栈

| 层 | 选型 |
|------|------|
| 后端（数据中台 / 调度） | Go 1.24、自研 `app/infra/go/application` 框架 |
| 后端（行情 / 知识图谱） | Python ≥ 3.10、FastAPI / Uvicorn |
| 前端 | Angular 17（Standalone + Signals）、ng-zorro-antd、ECharts / ngx-echarts |
| 关系数据库 | PostgreSQL 16 |
| 时序引擎 | TimescaleDB（日线 / 分钟级行情自动分区 + 压缩） |
| 语义检索 | PGVector（文档 / 公司名 embedding） |
| 图数据库 | Neo4j（产业链关系网络，atlas 专属） |
| 对象存储 | MinIO（2.7TB，财报 / 研报 / 新闻原始文件） |
| LLM 编排 | NVIDIA NIM、OpenRouter、智谱 GLM、本地 Ollama（OpenAI 兼容适配） |
| PDF 处理 | pdfplumber（默认）、layout sidecar、RapidOCR / PyMuPDF（质量门控触发） |
| 部署 | Docker Compose、Jenkins CI、单机多虚拟机 |
| 编排 / 调度 | 自研 cronjob（秒级 Cron、同步/异步回调、并发控制） |

> 不引入 ClickHouse / Qdrant——当前数据量在 PostgreSQL 生态内可充分满足。

---

## 各服务说明

| 服务 | 语言 | 端口 | 职责 |
|------|------|------|------|
| **phoenixA** | Go | 18085 | 数据中台：所有 DB 的 CRUD 网关，原始字段治理（`data_field_dictionary`）、特征注册中心与运行态、迁移管理；其他服务通过 HTTP 调用，禁止直连数据库 |
| **artemis** | Python | 18000 | 多源行情拉取与缓存、回测引擎、特征平台执行框架、杜邦分析等计算服务 |
| **atlas** | Python | 18400 | 研报知识生产与受控查询：开发期字段发现、生产期严格抽取、实体解析、Claim 构建与图投影编排 |
| **cronjob** | Go | 19999 | 定时任务调度中心：秒级 Cron、同步执行 / 异步回调、并发策略（QUEUE / SKIP / PARALLEL）、超时与重试、运行实例持久化 |
| **cthulhu** | Angular | 4200 | 前端 UI：行情 / 图谱 / 回测 / 信号 / 洞察 / 调度管理等工作台 |

### phoenixA — 数据中台

- 所有持久化的唯一收口：atlas、artemis 均不直连数据库，通过 HTTP 调用 phoenixA。
- 原始字段契约 `govern.data_field_dictionary` 是权威，不为每个字段复制一份 Feature 定义。
- 特征治理：已发布 FeatureVersion 为不可变运行契约，YAML Manifest 经 Git/Code Review 后由 Registry Sync 投影到数据库。
- JSONB 列统一存 object 并加 `jsonb_typeof` CHECK 约束，保证可按 key 查询。
- 维护独立的迁移跟踪与生产 preflight / rebaseline 脚本。

### artemis — 行情与计算

- 多源行情采集、缓存与落库（日线 / 分钟级 Bars 以 `security_id` 为物理身份，Timescale 自动分区）。
- 特征平台执行框架：独立于旧 Factor/Regime 重新设计，支持 `python` 实现并预留 `expression / vendor / model / llm`。
- 信号研究：T 信号单日回放工作台、事件研究统计（命中率 / MFE / MAE / 多期限覆盖）、杜邦财务分析。

### atlas — 研报知识图谱

Atlas 有两个明确生命周期：

- **开发期采样（Sampling）**：对六种 `report_type`（股票 / 行业 / 宏观 / 新股 / 策略 / 早报）逐 PDF 生成自由 JSON，再按类型归纳可复用字段、审核并发布 extraction profile。开发环境可用只读身份读取生产目录与生产 MinIO，结果只写开发库。
- **生产期严格抽取**：只使用已审核、不可变、按类型划分的 profile。生产配置强制 `sampling_enabled: false`，后端不注册 Sampling API，Cthulhu 生产构建也不提供 Sampling 页面。

关键能力：

- **可插拔多模型 LLM Harness**：NVIDIA NIM、OpenRouter、智谱、本地 Ollama 通过 OpenAI 兼容适配接入；多 key 池 + per-key 限流 + 失败计数 + 熔断降级 + 透明 failover。缺失 / 限流 / 退役的模型只降低容量而不禁用采样；provider 成功要求阶段级 JSON 解析与证据校验，schema 不兼容会 failover 而非毒化运行。
- **两阶段自由抽取**：每篇 PDF 先产出模型自撰、独立可读的 JSON（长文档用代表页 map/merge、有界 token 预算、断点续跑、截断 JSON 安全恢复）；再由跨文档 reviewer 归纳为 `CORE` / `CONDITIONAL` 字段，保留证据文档/路径链接，拒绝元数据与过度具体命名。
- **PDF 解析 Harness**：默认 pdfplumber；空 / 稀疏 / 图表标签主导的文档经页级文本质量门控后升级到 layout sidecar 或本地 OCR，仅当输出确实提升可用文本时才接受回退。OCR 为可选依赖组而非生产基线。
- **Claim / 图谱管线**：实体解析、别名、证券关联、Relation/Quantified/Analyst View Claim 构建，并投影到 Neo4j；不暴露任意 Cypher 执行。

### cronjob — 调度中心

- 秒级 Cron 表达式（6 字段，兼容 5 字段自动补秒），仅当前秒判定、不追赶丢失触发。
- 同步任务：HTTP 请求完成判定成功 / 失败 / 超时；异步任务预留回调闭环（token 校验）。
- 并发控制：最大并发 + 策略（QUEUE / SKIP / PARALLEL）；支持手动触发、运行实例查询、状态机管理。
- 任务与运行记录持久化（MySQL）。

### cthulhu — 前端

- Angular 17 原生能力起步（Standalone + Signals），按业务域垂直特性切片，暂不引入 NgRx。
- 对 ng-zorro-antd 做最小包装形成领域可复用 UI，避免业务层散落 `nz-` 属性。
- 图表封装基于 ECharts / ngx-echarts；懒加载路由 + Signals 减少变更检测。
- 现有特性模块：`artemis` / `atlas` / `bi` / `cronjobs` / `feature-platform` / `phoenixa` / `workbench`。

---

## 数据源

| 数据 | 来源 |
|------|------|
| A 股研报列表与详情、研报 PDF | 东方财富（Eastmoney） |
| A 股历史行情 / 分钟线 | Baostock、akshare |
| 实时行情 | 新浪（Sina） |
| 分钟级上下文 / 同分钟相对量 | AmazingData |
| 全球期货 / 外汇 / 指数 / 收益率 / 利差 | 标准化 Bars 与 `market_observation_daily`（通过 `security_registry` 治理） |

数据工程要点：游标去重与高产日冻结修复、退市研报 404 终态处理（`ReportGone` 立即终止、不重试不退避，避免拖垮调度回调时限）、迁移版本管理、生产 preflight / rebaseline 脚本。

---

## 基础设施与部署

**物理机**：Dell R730，双路 Xeon E5-2683 v4（32 核 64 线程），128 GB RAM。

**虚拟机划分**（单机三 VM，DB 与应用做 IO / 内存隔离）：

| 虚拟机 | 内存 | 存储 | 用途 |
|--------|------|------|------|
| VM1 Docker 服务 | 48 GB | 512GB NVMe + 2.7TB（MinIO 挂载） | phoenixA / artemis / atlas / cronjob / cthulhu(nginx) / neo4j / minio 容器 |
| VM2 数据库 | 48 GB | 2TB NVMe（热）+ 8TB SATA SSD（温/冷+备份） | PostgreSQL 16 + TimescaleDB + PGVector |
| VM3 开发机 | 16 GB | 512GB NVMe 剩余 | 开发环境 |
| 预留 | 16 GB | - | Kafka / Flink 或紧急扩容缓冲 |

**存储分层**：512GB NVMe（服务 VM）+ 2TB NVMe（数据库热数据）+ 8TB SATA SSD（温/冷与备份）+ 2.7TB MinIO（对象存储）。PostgreSQL `shared_buffers` 12GB、`effective_cache_size` 36GB，依赖 OS 页缓存读热数据；Neo4j 与 atlas 同处一个 Docker 网络以零延迟 Bolt 直连。

**部署方式**：每个服务一份 Dockerfile（`deploy/docker/dockerfile/`）与 docker-compose（`deploy/docker/docker-compose/`），Jenkins（`deploy/jenkins/`）与 Python 部署脚本（`deploy/scripts/deploy_*.py`）驱动构建与发布。

---

## 快速开始

> 仓库根目录提供共享 Python 虚拟环境 `venv/`，Go 服务使用各项目 `vendor/`。

### 1. 克隆与依赖

```bash
git clone <repo-url> chaos && cd chaos

# Python 服务（artemis / atlas）
python -m venv venv && source venv/bin/activate
pip install -e app/projects/artemis[dev]
pip install -e app/projects/atlas[dev]
# OCR 为可选依赖组
pip install -r app/projects/atlas/requirements-ocr.txt   # 可选

# Go 服务（phoenixA / cronjob）
# 需要 Go 1.24，依赖已在各项目 vendor/ 中

# 前端（cthulhu）
cd app/projects/cthulhu && npm install
```

### 2. 本地启动各服务

每个服务提供三套配置：`config.yaml`（默认）、`config-home.yaml`（本机开发）、`config-production.yaml`（生产）。本机开发使用 `config-home.yaml`。

```bash
# phoenixA（Go 数据中台）
cd app/projects/phoenixA && go run ./cmd -c config/config-home.yaml

# cronjob（Go 调度中心）
cd app/projects/cronjob && go run ./cmd -c config/config-home.yaml

# artemis（Python 行情/计算）
PYTHONPATH=app/projects/artemis venv/bin/python -m artemis.main \
  -c app/projects/artemis/config/config-home.yaml

# atlas（Python 知识图谱）
PYTHONPATH=app/projects/atlas venv/bin/python -m atlas.main \
  -c app/projects/atlas/config/config-home.yaml

# cthulhu（Angular 前端）
cd app/projects/cthulhu && ng serve   # http://localhost:4200
```

### 3. Docker 部署

```bash
cd deploy/docker/docker-compose
docker compose -f phoenixA.yaml up -d
docker compose -f atlas.yaml up -d
# artemis.yaml / cronjob.yaml 同理
```

生产构建前端：

```bash
cd app/projects/cthulhu && ng build        # 产物输出到 dist/
bash ../../../deploy/scripts/deploy-cthulhu.sh
```

---

## 目录结构

```
chaos/
├── app/
│   ├── infra/                  # 跨服务基础设施（Go application 框架、proto 等）
│   └── projects/
│       ├── artemis/            # 行情拉取 / 回测 / 特征平台（Python）
│       ├── atlas/              # 研报知识图谱 / LLM 抽取（Python）
│       ├── cronjob/            # 定时调度中心（Go）
│       ├── cthulhu/            # 前端 BI（Angular 17）
│       └── phoenixA/           # 数据中台 / DB 网关（Go）
├── deploy/
│   ├── docker/                 # Dockerfile 与 docker-compose
│   │   ├── dockerfile/
│   │   └── docker-compose/
│   ├── jenkins/                # CI 脚本
│   └── scripts/                # 部署脚本（deploy_*.py / deploy-cthulhu.sh）
├── docs/
│   ├── system_design/          # 平台级架构与迭代设计
│   ├── installation/           # 安装与配置
│   ├── strategies/             # 策略笔记
│   └── third_party_sdk/        # 第三方 SDK 对接
├── protos/                     # gRPC / 接口定义
├── venv/                       # 共享 Python 虚拟环境
└── README.md
```

每个子项目自带 `README.md`、`CHANGELOG`、`docs/`、`config/`、`tests/`，详见各项目目录。

---

## 文档导航

### 平台级（`docs/system_design/`）

- [`2026-04-29 DESIGN_OF_FINANCIAL_QUANT_PLATFORM.md`](docs/system_design/2026-04-29%20DESIGN_OF_FINANCIAL_QUANT_PLATFORM.md) — 总体设计与系统全景
- [`2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md`](docs/system_design/2026-04-29%20INFRASTRUCTURE_AND_DATA_ENGINE.md) — 硬件资产、虚拟机规划与数据引擎选型
- [`2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md`](docs/system_design/2026-07-14%20FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md) — 特征平台架构与分阶段迭代
- [`2026-07-18 FEATURE_PLATFORM_OPERATIONS_RUNBOOK.md`](docs/system_design/2026-07-18%20FEATURE_PLATFORM_OPERATIONS_RUNBOOK.md) — 运维手册
- [`2026-07-18 FEATURE_PLATFORM_PHASE_5_ACCEPTANCE_REPORT.md`](docs/system_design/2026-07-18%20FEATURE_PLATFORM_PHASE_5_ACCEPTANCE_REPORT.md) — Phase 5 验收报告
- [`2026-07-28 RISK_INTELLIGENCE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md`](docs/system_design/2026-07-28%20RISK_INTELLIGENCE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md) — 风险智能平台架构（设计阶段）

### Atlas（`app/projects/atlas/docs/`）

- [`2026-08-13 ARCHITECTURE_DESIGN_FOR_ATLAS_V3.md`](app/projects/atlas/docs/2026-08-13%20ARCHITECTURE_DESIGN_FOR_ATLAS_V3.md) — Atlas V3 现行架构设计
- [`DEPLOYMENT.md`](app/projects/atlas/docs/DEPLOYMENT.md) — 部署说明
- [`2026-08-13 ATLAS_SAMPLING_VALIDATION.md`](app/projects/atlas/docs/2026-08-13%20ATLAS_SAMPLING_VALIDATION.md) — 真实采样验收

---

## 开发与测试

```bash
# Atlas
cd app/projects/atlas && PYTHONPATH=. ../../../venv/bin/python -m pytest tests -q

# Artemis
cd app/projects/artemis && PYTHONPATH=. ../../../venv/bin/python -m pytest tests -q

# Go 服务（注意：导入 app/infra/go/application 的包直接 go test 会报框架级
# -test.testlogfile 未定义，请在子包内或复制到 /tmp 验证纯逻辑）
cd app/projects/phoenixA && go test ./internal/...

# 前端（修改模板后 tsc 不报模板绑定错，必须 ng build 才能抓 NG8xxx）
cd app/projects/cthulhu && ng build
```

约定：

- 数据库变更走迁移文件（phoenixA 有 `_migrations` 跟踪表，已应用的 `.sql` 不重跑；cronjob 无跟踪、每次重跑全部）。
- `data_json` JSONB 列必须存 object 并加 CHECK 约束。
- 生产配置 fail-closed：采样启用时生产 API 不注册 sample 路由，Cthulhu 生产构建不提供 sample 导航。
- 定时任务时间列使用 `timestamp without tz` + 容器 `TZ=Shanghai`，读取时注意 8h 偏移与去重。

---

## 版本与路线图

- **已完成**：数据中台与治理、多源行情采集、研报知识图谱（两阶段 LLM 抽取 + 采样工作流）、特征平台 Phase 0–5、信号研究与回测工作台、杜邦分析、定时调度、前端 BI。
- **设计中**：风险智能平台（多主体、多期限 1/5/20/60 日风险度量，输出概率 / 严重度 / 置信度 / 证据，与投资策略严格解耦），拟新增独立风险服务 Aegis。
- **预留**：Kafka / Flink 流处理（16GB 未分配内存）、DSL / AST 特征表达式引擎、微前端插件化。

各服务版本与变更见对应 `CHANGELOG`。

---

## 许可

见 [LICENSE](LICENSE)。
