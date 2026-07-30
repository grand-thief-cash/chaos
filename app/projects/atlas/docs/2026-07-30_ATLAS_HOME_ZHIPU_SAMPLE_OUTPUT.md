# Atlas Home：智谱文本抽取与 Sample 审核输出

本文件记录 2026-07-30 对 Phase 1 设计的运行时调整，优先级高于原设计中
“PDF_DIRECT only”和“不持久化模型抽取 JSON”的限定。

## 输入与模型

- `chaos-dev` 是 Artemis 下载任务写入的原始 PDF bucket。
- `glm-4.7-flash` 是当前 Atlas 所有模型任务统一使用的模型。
- 该模型是文本模型，因此抽取客户端先在内存中用 `pdfplumber` 提取每页文本，
  插入显式页码标记，再调用智谱 Chat Completions JSON 模式。
- Extraction Run 的 `input_mode` 记录为 `TEXT_EXTRACTED`，不伪装为直接 PDF 输入。
- 不生成本地临时 PDF、长期 normalized document 或 chunk。

## Sample 输出

每个 Sample/Discovery Run 在每份 PDF 处理完成后，立即写一份审核 JSON：

```text
s3://atlas-dev/sample_output/YYYYMMDD/{report_type}/{resource_id}.json
```

成功和失败文档都会写入。JSON envelope 包含：

- Discovery Run ID 与采样时间。
- 原始研报元数据。
- Extraction Run 状态、错误和统计。
- 通过校验的 extraction result；失败时为 `null`。
- 聚合前的单文档 discovery result。

对象 key 同时写回 `DiscoveryDocumentResult.sample_output_object_key`，供后续
Cthulhu 页面列出并打开人工审核对象。

## 配置

家庭环境使用 `config/config-home.yaml`：

```bash
python -m atlas.main -c config/config-home.yaml
```

配置中的 API key 可由 `ZHIPU_API_KEY` 环境变量覆盖。源码和日志不得输出 key、
MinIO secret 或完整 PDF 正文。

可复用的真实环境 smoke test：

```bash
python scripts/live_home_smoke.py
python scripts/live_home_smoke.py --check-phoenixa --skip-model-probe
python scripts/live_home_smoke.py --run-model --write-sample --max-types 1 --attempts 2
python scripts/live_home_smoke.py --run-model --write-sample --types stock --attempts 2
python scripts/live_home_smoke.py --run-model --write-sample --types macro --model-timeout 300
```

脚本不依赖 PhoenixA：它验证两个 bucket、统计 `chaos-dev` 的 PDF 类型分布、
调用 agent JSON probe；显式启用 `--run-model` 后再选代表 PDF 走真实解保护、
文本提取、Atlas Schema 校验，并可把结果写到 `atlas-dev`。
