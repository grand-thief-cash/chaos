## 十六、结构化查询 API

以下 API 由 Atlas 对 cthulhu/Query Agent 暴露。需要图遍历时，Atlas 的 `graph_repository` 调用 phoenixA 预定义 Graph Query API；Atlas 和 Query Agent 都不直接连接 Neo4j，也不接受任意 Cypher。

### 16.1 实体解析

```http
GET /api/v1/atlas-kg/entities:resolve?name=英伟达
GET /api/v1/atlas-kg/entities/{entity_id}
GET /api/v1/atlas-kg/entities/{entity_id}/aliases
```

### 16.2 公司画像

```http
GET /api/v1/atlas-kg/companies/{entity_id}/profile
```

返回：

- 公司基本实体信息。
- 关联证券。
- 产品。
- 使用的材料和技术。
- 所属外部行业分类。
- 参与的价值链。
- 客户、供应商和竞争者。
- 量化 Claim 摘要。
- 分析师观点摘要。

### 16.3 上下游查询

```http
GET /api/v1/atlas-kg/companies/{entity_id}/suppliers
GET /api/v1/atlas-kg/companies/{entity_id}/customers
GET /api/v1/atlas-kg/companies/{entity_id}/competitors
GET /api/v1/atlas-kg/companies/{entity_id}/products
GET /api/v1/atlas-kg/companies/{entity_id}/inputs
```

### 16.4 价值链查询

```http
GET /api/v1/atlas-kg/value-chains/{entity_id}
GET /api/v1/atlas-kg/value-chains/{entity_id}/graph?depth=2
GET /api/v1/atlas-kg/companies/{entity_id}/value-chain-context
```

### 16.5 Claim 查询

```http
GET /api/v1/atlas-kg/claims/relations
GET /api/v1/atlas-kg/claims/quantified
GET /api/v1/atlas-kg/analyst-views
```

过滤参数：

```text
entity_id
predicate
metric
assertion_type
source_document_id
published_from
published_to
status
```

---
