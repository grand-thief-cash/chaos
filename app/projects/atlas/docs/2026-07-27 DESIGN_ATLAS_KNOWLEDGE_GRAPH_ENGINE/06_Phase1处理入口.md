## 六、Phase 1 处理入口

### 6.1 主入口：后台消费任务

Phase 1 优先使用简单、可恢复的轮询任务，不引入消息队列或 Outbox。

```text
定时任务
    ↓
Atlas Report Consumer
    ↓
调用 phoenixA：
查询已下载、MinIO 对象可用、且 Atlas 未成功处理的研报
    ↓
为每份文档创建 document_extraction_run
    ↓
进入 Extraction Orchestrator
```

推荐内部入口：

```http
POST /internal/v1/atlas-kg/jobs/consume-research-reports
```

请求示例：

```json
{
  "published_from": "2025-01-01",
  "published_to": "2026-07-27",
  "report_types": null,
  "limit": 100,
  "force": false
}
```

说明：

- `report_types=null` 表示从 Active Semantic Version 的 `report_type_profiles` 中解析全部 `enabled_for_production=true` 的 Artemis report type，不表示消费全部六类。
- Active Semantic Version 中没有启用类型时，任务以 `NO_ENABLED_REPORT_TYPES` 拒绝启动，不能静默回退为全部类型。
- 显式传入 `report_types` 只用于受控测试或运维过滤，且必须是 Active Semantic Version 已启用类型的子集；生产接口不能借此绕过 Sample 结论。
- 六类候选研报的具体枚举由 Artemis 文档元数据传递，Atlas 不复制硬编码另一套名称。
- 每个类型是否启用、为何启用、使用哪个 Prompt Profile，都由 Sample/Discovery 结果进入 Semantic Version 后确定。
- Atlas 可以按报告类型路由不同 prompt，但必须通过配置映射。
- `force=false` 时遵守幂等规则。

### 6.2 手动单文档入口

用于调试、重跑和质量抽查：

```http
POST /api/v1/atlas-kg/extraction-runs
```

```json
{
  "source_document_id": "phoenixA_document_id",
  "pipeline_version": "atlas-kg-v1",
  "force": false
}
```

### 6.3 批次状态查询

```http
GET /api/v1/atlas-kg/extraction-runs/{run_id}
GET /api/v1/atlas-kg/extraction-runs?status=FAILED
GET /api/v1/atlas-kg/extraction-runs?source_document_id=...
```

### 6.4 Graph 重建入口

```http
POST /internal/v1/atlas-kg/graph-projections
```

```json
{
  "mode": "incremental",
  "claim_updated_after": "2026-07-27T00:00:00Z"
}
```

支持：

- `incremental`：只处理新增或变更 Claim。
- `full_rebuild`：清空 Atlas 图谱投影并从有效 Claim 重建。

`full_rebuild` 属于受控运维操作，不暴露给 Query Agent。

---
