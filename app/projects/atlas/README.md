# Atlas

Atlas 是 Chaos 的研报知识生产与受控查询服务。Artemis 负责下载 PDF 到 MinIO 并登记研报元数据；Atlas 负责开发期字段发现、生产期严格抽取、实体解析、Claim 构建和图投影编排，所有持久化与图访问都通过 PhoenixA 完成。

## 当前设计

Atlas 有两个明确生命周期：

- **Development/Test Sampling**：对六种 `report_type` 逐 PDF 生成自由 JSON，再按类型归纳可复用字段、审核并发布 extraction profile。开发环境可使用专用只读身份读取生产 PhoenixA 目录和生产 MinIO，结果只写开发 PhoenixA。
- **Production Full Extraction**：只使用已审核、不可变、按类型划分的 profile。生产配置强制 `sampling_enabled: false`，后端不注册 Sampling API，Cthulhu 生产构建也不提供 Sampling 页面。

模型调用由可插拔 Harness 编排，支持 NVIDIA NIM、OpenRouter、Zhipu 和本地 Ollama 的多模型、多 key、失败降级；PDF 默认走 pdfplumber，只有质量门控触发时才升级到 layout sidecar 或本地 OCR。

Bootstrap semantic YAML 不启用任何正式研报类型。候选字段目录不能自动进入生产，必须人工 Review、发布新 Semantic YAML，并显式切换 `semantic_config_path`。

## 工程入口

```bash
cd /home/machine/projects/chaos
PYTHONPATH=app/projects/atlas venv/bin/python -m atlas.main \
  -c app/projects/atlas/config/config-home.yaml
```

运行测试：

```bash
cd /home/machine/projects/chaos/app/projects/atlas
PYTHONPATH=. ../../../venv/bin/python -m pytest tests -q
```

## 文档

- 现行架构设计：[`docs/2026-08-13 ARCHITECTURE_DESIGN_FOR_ATLAS_V3.md`](docs/2026-08-13%20ARCHITECTURE_DESIGN_FOR_ATLAS_V3.md)
- 部署说明：[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- 真实 Sampling 验收：[`docs/2026-08-13 ATLAS_SAMPLING_VALIDATION.md`](docs/2026-08-13%20ATLAS_SAMPLING_VALIDATION.md)
- 候选字段目录（未批准生产）：[`docs/2026-08-13 ATLAS_SAMPLING_CANDIDATE_FIELD_CATALOG_V1.json`](docs/2026-08-13%20ATLAS_SAMPLING_CANDIDATE_FIELD_CATALOG_V1.json)
