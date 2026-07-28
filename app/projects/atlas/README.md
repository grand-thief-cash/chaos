# Atlas

Atlas 是 Chaos 的研报知识生产与查询服务。Artemis 负责下载 PDF 到 MinIO 并在 phoenixA 记录下载状态；Atlas 消费 PDF、完成语义发现/抽取/实体解析/Claim 构建，并通过 phoenixA 写 PostgreSQL 和 Neo4j。Atlas 不直接连接数据库。

## Phase 1 范围

- Whole-PDF 模型抽取；pikepdf 只在内存中解除 owner permission。
- Sample 驱动的报告类型选择、Predicate/Concept proposal、人工审核和版本 YAML 发布。
- 申万/东财/券商分类的模型 Crosswalk 与程序化完整性校验。
- 全球上市和非上市公司统一实体、别名与 security_registry 链接。
- 事实、量化主张和分析师观点分离；只有允许的事实 Claim 投影到图。
- 固定图查询工具和只读 Query Agent；不接受任意 Cypher。
- Event/Impact Engine 留到后续阶段。

Bootstrap semantic YAML 不启用任何正式研报类型。必须先运行 Sample、
在 Cthulhu 完成人工 Review 并发布新 YAML，再通过部署配置切换
`semantic_config_path`，批量消费入口才会处理正式 PDF。

## 工程入口

```powershell
C:\Users\gaoc3\projects\chaos\.venv\Scripts\python.exe -m atlas.main -c config/config.yaml
```

配置加载和启动参数参考 Artemis 约定，但 Atlas 保留自己的领域目录：

```text
atlas/
├── api/http_gateway
├── application
├── core/clients
├── knowledge_production
├── knowledge_store
├── intelligence
└── models
```

运行测试：

```powershell
C:\Users\gaoc3\projects\chaos\.venv\Scripts\python.exe -m pytest app/projects/atlas/tests -q
```

部署说明：[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

设计文档入口：[`docs/2026-07-27 DESIGN_ATLAS_KNOWLEDGE_GRAPH_ENGINE/00_头部.md`](docs/2026-07-27%20DESIGN_ATLAS_KNOWLEDGE_GRAPH_ENGINE/00_%E5%A4%B4%E9%83%A8.md)
