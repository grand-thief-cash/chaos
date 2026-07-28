## 二十九、TODO：实体补全闭环

未来 Atlas 遇到高价值 unresolved company 时：

```text
Atlas
  → entity_enrichment_requested
  → Artemis 获取官方页面/公告/注册资料
  → MinIO + phoenixA
  → Atlas 重新解析
  → 更新 entity/alias/identifier
  → 重新解析待定 Claim
  → Graph 增量更新
```

Phase 1 不实现自动外部搜索，只保留 unresolved mention 和重新解析能力。

---

