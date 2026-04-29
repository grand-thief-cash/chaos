# Atlas — 产业链知识图谱引擎

## 概述

Atlas 是一个面向投资分析的产业链知识图谱引擎。它从财报、研报、新闻、公告中抽取结构化信息，
构建「资源—产品—公司—市场—事件」的产业链知识图谱，并通过每日新闻/事件更新，
提供「事件 → 公司影响分析」和「公司 → 发展综述」两大核心能力。

## 架构

```
文档 (PDF/HTML/文本)
        ↓
   文档预处理 (解析+切分)
        ↓
   LLM 结构化抽取 (industry_extraction_skills.md)
        ↓
   实体融合 + 去重
        ↓
   Neo4j 知识图谱
        ↓
   查询 / 影响分析 / 投资洞察
```

## 核心能力

1. **文档摄入** — 支持 PDF/HTML/纯文本，自动切分并调用 LLM 抽取
2. **知识图谱构建** — 9 类实体节点 + 19 种标准关系
3. **每日更新** — 定时采集新闻，增量更新图谱
4. **事件影响分析** — 事件/政策沿产业链传导，评估对公司的正负影响
5. **公司发展综述** — 基于图谱数据生成投资视角的公司分析

## 快速启动

```bash
# 1. 启动 Neo4j
docker compose -f deploy/docker/docker-compose/atlas.yaml up -d neo4j

# 2. 安装依赖
cd app/projects/atlas && pip install -e ".[dev]"

# 3. 启动服务
python -m atlas.main -c config/atlas.yaml
```

## API 概览

| 模块 | 端点 | 说明 |
|------|------|------|
| 文档 | `POST /api/v1/documents/upload` | 上传文档 |
| 文档 | `POST /api/v1/documents/batch-extract` | 批量抽取 |
| 图谱 | `GET /api/v1/graph/company/{name}/chain` | 查询产业链 |
| 分析 | `GET /api/v1/analysis/event/{id}/impact` | 事件影响分析 |
| 分析 | `GET /api/v1/analysis/company/{name}/review` | 公司发展综述 |
| 洞察 | `GET /api/v1/insights/daily` | 每日投资洞察 |
| 流水线 | `POST /api/v1/pipeline/daily` | 触发每日更新 |

