## 二、Phase 1 核心决策

### 2.1 第一阶段做什么

Phase 1 包含：

- 将 Artemis 已下载并登记的六类研报视为候选输入，不假定六类都适合知识抽取。
- 在 Sample/Discovery 阶段按报告类型统计可读性、知识产出、Evidence 质量和重复信息比例，由模型给出启用建议，并由用户在发布 Semantic Version 时确认生产启用类型。
- 全量消费只领取 Active Semantic Version 中 `enabled_for_production=true` 的报告类型；未启用类型直接忽略，不创建 Extraction Run。
- 对进入抽取的 PDF 统一使用 `pikepdf` 在内存中重新序列化以解除可能存在的 owner permission/内容提取限制；`pikepdf` 不承担完整性、损坏或加密分类；不创建本地临时 PDF，也不保存第二份 MinIO 对象。
- 在模型端支持的前提下，将整份 PDF 直接提交 Qwen，不预先切块。
- 使用 Qwen3-14B Q4_K_M 作为主语义模型。
- 从研报中区分：
  - 事实陈述。
  - 公司披露。
  - 管理层计划或指引。
  - 分析师估计。
  - 分析师观点。
  - 预测和情景假设。
- 抽取公司、产品、材料、技术、市场等知识实体。
- 以 phoenixA `security_registry` 作为 A 股公司种子。
- 渐进建立 Atlas 自己的知识实体及别名。
- 抽取和归一化公司、产品、材料、技术之间的关系。
- 抽取产能、产量、销量、市占率等量化 Claim。
- 从可选规模的研报样本中自动总结：
  - 需要全量抽取的字段。
  - Predicate。
  - Metric。
  - Analyst View Type。
  - Product/Material/Technology/Industry Concept。
- 在 cthulhu 中审核语义 Proposal、确认生产报告类型、观察行业 Crosswalk 结果并处理异常实体歧义。
- 发布不可变 Semantic Version，并导出运行时 YAML。
- 构建申万、东财和研报/券商行业概念到 Atlas Industry Concept 的 Crosswalk。
- 保存标准化 Claim，而不是保存 LLM 原始响应。
- 将已接受的 Claim 通过 phoenixA 的图存储接口投影到 Neo4j。
- 提供公司、上下游、产品、竞争关系等结构化查询。
- 提供基于受控工具的 Atlas Query Agent。
- 提供公司产业链综述和研报观点总结。
- 提供 cthulhu Atlas 页面：
  - Sample/Discovery Run。
  - Semantic Proposal Review。
  - Semantic Version Publish。
  - Industry Crosswalk Quality / Exception Review。
  - Entity Resolution Review。
  - Extraction Run Monitoring。
  - Graph Explorer。
  - Company Review / Query Agent。

### 2.2 第一阶段明确不做什么

Phase 1 不包含：

- 新闻和政策事件处理。
- EventMention、CanonicalEvent、EventRevision 的正式实现。
- Event fingerprint 和事件去重。
- 油价、金价、期货等时间序列信号生成。
- Impact Engine。
- 利好、利空和影响时间尺度判断。
- 向量生成和向量数据库。
- normalized document 长期持久化。
- chunks 长期持久化。
- LLM 原始响应持久化。
- parser 调试图片持久化。
- bbox 和 chunk 级 Evidence 子系统。
- Docling、Marker 等复杂版面解析作为必选依赖。
- 图片、图表、复杂表格的深度理解。
- DeepSeek 或其他模型的全量二次复核。
- 完整全球公司主数据预构建。
- 基于 Chunk 的主抽取链路；只有整份 PDF 实测失败后才重新评估。
- 面向所有知识领域的通用 Ontology 管理平台。
- 通用的跨系统 Agent 平台。

### 2.3 最小持久化原则

Phase 1 只持久化对知识生产、查询和图谱重建有直接价值的数据。

| 数据 | Phase 1 是否保存 | 存储位置 |
|---|---:|---|
| 原始 PDF | 已由 Artemis 保存 | MinIO |
| PDF 下载记录和对象地址 | 已由 Artemis/phoenixA 保存 | phoenixA |
| 内存解保护后的 PDF bytes | 否，LLM 请求完成后立即释放 | 进程内存 |
| normalized document | 否 | 不生成 |
| chunks | 否 | 不生成 |
| LLM 原始响应 | 否，校验并转换后丢弃 | 内存 |
| parser 调试图片 | 否 | 不生成 |
| 文档抽取运行状态 | 是 | PostgreSQL |
| 知识实体和别名 | 是 | PostgreSQL |
| 标准化关系 Claim | 是 | PostgreSQL |
| 标准化量化 Claim | 是 | PostgreSQL |
| 分析师观点 | 是 | PostgreSQL |
| Semantic Discovery Run/Proposal/Version | 是 | PostgreSQL |
| 发布后的 Semantic YAML | 是 | MinIO 或部署配置目录 |
| 行业体系、概念和 Crosswalk | 是 | PostgreSQL + 发布 YAML |
| 最小 Evidence（页码+短原文） | 是，嵌入 Claim | PostgreSQL |
| Neo4j 图谱 | 是，但属于派生数据；由 phoenixA 统一访问 | Neo4j |
| Embedding | 否 | TODO |

关于 Evidence 的收敛决策：

- 不建设 `claim_evidence` 表。
- 不保存 bbox。
- 不保存 chunk 引用。
- 但为了控制模型幻觉、支持 cthulhu 审核，每条 Claim/View 必须保存一段短 `evidence_quote` 和可空 `page_number`。
- 这部分存储量远小于 normalized/chunks，却是人工判断模型是否胡编的必要信息。

接受以下工程权衡：

- 更换 prompt 或重新抽取时，重新读取原始 PDF 并提交模型。
- Phase 1 先用真实样本验证整份 PDF 直读的成功率、耗时和输出质量。
- Sample 阶段必须同时产出报告类型启用建议；生产任务不得默认回退为“消费全部六类”。
- PDF 大小不能完全代表页数或模型上下文；超限文档必须显式失败，不能静默截断。
- LLM 抽取结果一旦通过校验，应转换为标准化 Claim；原始模型响应不作为系统资产。
- Neo4j 出现问题时，由 Atlas 从 PostgreSQL 中的有效 Claim 重新生成投影请求，并经 phoenixA 重建。

---
