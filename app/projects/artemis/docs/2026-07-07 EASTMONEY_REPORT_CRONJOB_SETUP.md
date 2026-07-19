# Eastmoney 研报下载任务 — cronjob 调度配置

本文说明如何通过 cronjob REST 接口把 `STOCK_ZH_A_EASTMONEY_REPORT` 任务接入定时调度。
**cronjob 侧无需改代码** —— 调度配置全部存在 cronjob 的 `tasks` 表里，通过 REST 创建即可。

任务自身的全量/增量策略由 artemis 任务自决（参考 `STOCK_ZH_A_HIST_PARENT` 的自决模式）：
- LIST 阶段以 phoenixA 中 `MAX(publish_date)`（任意状态）为游标，每次只拉取新增研报元数据；
- PROCESS 阶段取最早 N 份 pending/error 研报，详情→PDF→MinIO→phoenixA 标记 downloaded；
- 全量回补在多次运行中完成，断点续传，不会卡在旧页。

因此 cronjob 只需**用一个高频 cron 反复触发同一个任务**，全量和增量共用同一套策略。

---

## 1. 创建任务（POST /api/v1/tasks）

向 cronjob 发起请求（默认创建为 DISABLED，需再 enable）：

```bash
curl -X POST http://127.0.0.1:9999/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stock_zh_a_eastmoney_report",
    "description": "东财研报下载（高频运行，全量+增量同一策略）",
    "cron_expr": "0 0 */2 * * *",
    "timezone": "Asia/Shanghai",
    "exec_type": "ASYNC",
    "method": "POST",
    "target_service": "artemis",
    "target_path": "/tasks/run/STOCK_ZH_A_EASTMONEY_REPORT",
    "body_template": "{}",
    "max_concurrency": 1,
    "concurrency_policy": "SKIP",
    "overlap_action": "SKIP",
    "failure_action": "RUN_NEW"
  }'
```

字段说明：
- `cron_expr`：6 字段（秒 分 时 日 月 周）。常用档位：
  - 每小时：`0 0 * * * *`
  - 每 2 小时：`0 0 */2 * * *`（推荐，回补与增量兼顾）
  - 每 4 小时：`0 0 */4 * * *`（较保守）
- `exec_type: "ASYNC"`：研报下载受东财反爬限速，单次运行可达数分钟~十几分钟，必须用 ASYNC（后台线程 + callback 回调），避免 SYNC 的 15 分钟卡死超时。cronjob 的 `callback_timeout_sec` 需设到足够大（如 3600s）。
- `target_path` = `/tasks/run/{TASK_CODE}` —— artemis 接收端点。
- `body_template: "{}"`：任务自决日期范围，无需传参；如需覆盖可传 `{"start_date": "...", "download_limit": 50}`。
- `max_concurrency: 1` + `overlap_action: "SKIP"`：东财反爬，禁止并发/重叠运行。

## 2. 启用任务

```bash
# 用第 1 步返回的 task id
curl -X PATCH http://127.0.0.1:9999/api/v1/tasks/{id}/enable
```

启用后调度器每次 tick 扫描到该任务，到点即触发。

> 也可以用导入接口批量创建：仓库已附导出文件
> `app/projects/artemis/artemis/engines/task_engine/download/tasks_export_2026-07-07-eastmoney-report.json`
> （默认 `status: DISABLED`，导入后需手动 enable）。导入接口是 **multipart file 上传**（不是 JSON body）：
> ```bash
> curl -X POST http://127.0.0.1:9999/api/v1/tasks/import \
>   -F "file=@app/projects/artemis/artemis/engines/task_engine/download/tasks_export_2026-07-07-eastmoney-report.json"
> ```

## 3. 手动触发一次（联调）

不等 cron，立即跑一次（小批量）：

```bash
curl -X POST http://127.0.0.1:18000/tasks/run/STOCK_ZH_A_EASTMONEY_REPORT \
  -H "Content-Type: application/json" \
  -d '{"meta": {"run_id": 0, "task_id": 0, "exec_type": "SYNC"}, "body": {"download_limit": 3}}'
```

> 注：artemis `TaskMeta` 必填 `run_id`、`task_id`、`exec_type`（`task_code` 由 URL 路径注入，无需在 meta 传）。手动触发用 `0` 占位即可。

## 4. 回补耗时说明（重要）

东财反爬强制 PDF 下载间隔 9–18s + 详情页 7–15s，单份研报约 16–33s。
`download_limit=20` 时单次约 5–11 分钟（不含 LIST）。2 年滚动窗口研报量较大，
全量回补需多次运行累积完成 —— 调高 `download_limit` 或提高 cron 频率可加快，
但受限于反爬，不可激进。回补完成后，每次运行只处理少量新增研报，耗时很短。

## 5. 依赖前置

- phoenixA 已建 `ods.research_report_download_record` 表 + `/api/v2/research-report/*` 端点（见 phoenixA 迁移 `0006_research_report.sql`）。
- artemis `config.yaml` 中 `minio` 段已配置真实 endpoint（否则 MinioClient 退化为 Noop，PROCESS 阶段会被跳过——不抓详情/PDF、不落盘，研报停留在 pending；配好真实 MinIO 后下一次运行自动开始下载）。
- `pip install -r requirements.txt` 安装新增的 `minio`、`curl_cffi`。
