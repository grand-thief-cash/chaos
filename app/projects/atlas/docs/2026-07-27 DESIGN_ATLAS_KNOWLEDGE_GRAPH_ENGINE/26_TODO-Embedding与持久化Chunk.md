## 二十六、TODO：Embedding 与持久化 Chunk

Phase 1 不生成 Embedding，也不持久化 Chunk。

未来出现以下明确需求时再引入：

- 从原文中检索支持和反驳证据。
- 相似研报检索。
- 实体消歧候选召回。
- Event 语义候选召回。
- RAG 公司综述。
- 关系冲突检测。

届时需要：

- 定义稳定 chunk ID。
- 持久化 normalized document。
- 持久化 chunk text、page、heading、hash。
- 记录 embedding model/version/dimension。
- 支持重新 embedding 而不重新解析 PDF。

是否引入应由明确查询场景驱动，而不是为了“以后可能有用”提前建设。

---

