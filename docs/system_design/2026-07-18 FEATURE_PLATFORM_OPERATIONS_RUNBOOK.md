# Feature Platform 运维手册

> 状态：Phase 5 交付版
>
> 适用范围：PhoenixA v1.38.0、Artemis v0.47.0、Cthulhu Feature Workbench
>
> 权威设计：`2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md`

## 1. 平台边界

- PhoenixA 是 Feature Definition、Version、Implementation、Dependency、Run、RunItem、RunSubject 和 Value 的权威持久化服务。
- Artemis 是 Manifest 校验、依赖规划、插件执行、质量校验和异步任务编排服务。
- Cthulhu 是查询、诊断和手工触发工作台，不持有权威状态。
- `security_id` 是平台内永久身份。不得以 symbol 替代 RunSubject 身份。
- Published FeatureVersion 和已写入 Numeric Value 不可原地修改。修复业务定义必须发布新版本。

## 2. 配置与启动前检查

远端开发环境的配置入口：

```text
PhoenixA: app/projects/phoenixA/config/config-home.yaml
Artemis:  app/projects/artemis/config/config-home.yaml
```

启动前确认：

1. PhoenixA PostgreSQL datasource 可连接，`search_path` 包含 `ods,dwd,govern,kg,public`。
2. 开发库首次运行时启用 migration；Feature Platform 表由 `0008_feature_platform.sql` 创建。
3. 生产环境已由 DBA 准备 TimescaleDB 和 `warm_storage`，禁止依赖开发环境 fallback。
4. Artemis `engine.feature_platform.enabled=true`，`manifest_root` 指向 `config/feature_catalog`。
5. Artemis source profile 的 PhoenixA 地址指向当前版本，而不是只提供旧路由的遗留进程。
6. `ARTEMIS_CODE_REVISION` 应为部署 commit 或不可歧义的构建 revision。

不得在日志、Run parameters、Manifest implementation config 或 API 请求中写入密码、token、secret、DSN。开发配置中的现有明文凭证不得复制到新配置；生产部署必须改用环境变量或 secret manager 注入。

## 3. 标准验收命令

在仓库根目录执行：

```bash
export PATH=/usr/local/go/bin:/usr/bin:/bin
source /home/machine/projects/chaos/venv/bin/activate
cd /home/machine/projects/chaos/app/projects/artemis
PYTHONPATH=. python scripts/feature_platform_acceptance.py \
  --managed \
  --benchmark-requests 1000 \
  --benchmark-concurrency 16 \
  --benchmark-report-json /tmp/feature-platform-phase5-benchmark.json \
  --report-json /tmp/feature-platform-phase5-acceptance.json
```

`--managed` 会构建当前 PhoenixA，在 18085 启动隔离进程，并在 18084 启动当前 Artemis。它不会停止 8085、8084 或 4200 上已有进程。验收完成或失败时会终止隔离进程。

首次初始化空开发库时增加 `--run-migrations`。不要在未经 DBA 审查的生产库上使用该参数。

成功 Gate 包括：

- 两次 Manifest sync 幂等；
- Smoke V1 输出 1.0、V2 输出 2.0，各覆盖 10 个 RunSubject；
- 同请求复用同一 succeeded Run；
- latest 返回 V2，显式 V1 仍可查询；
- DataField PIT probe 的可用时间不越过 cutoff；
- 越界写入返回 `DATA_CUTOFF_VIOLATION`；
- Published V1 变更返回 `MANIFEST_CHECKSUM_CONFLICT`；
- PhoenixA 和 Artemis 重启后 Run、Value 和幂等结果不丢失；
- OpenAPI 与真实路由一致；
- 可选只读容量采样零错误。

## 4. Manifest 日常操作

### 4.1 仅校验

```bash
curl -sS -X POST http://127.0.0.1:8084/features/manifests/validate \
  -H 'Content-Type: application/json' \
  -d '{"source_profile":"default","check_entrypoints":true}'
```

必须检查 `valid=true`、`count` 符合预期，并阅读每个 Manifest 的 identity 和 checksum。

### 4.2 同步 Registry

```bash
curl -sS -X POST http://127.0.0.1:8084/features/registry/sync \
  -H 'Content-Type: application/json' \
  -d '{"source_profile":"default","check_entrypoints":true}'
```

响应字段语义：

| 字段 | 含义 | 运维动作 |
|---|---|---|
| `created` | 新定义或新版本已创建 | 检查版本状态和实现 |
| `updated_drafts` | Draft 被同步更新 | 发布前复核 diff |
| `unchanged` | checksum 相同 | 正常幂等结果 |
| `rejected` | 单个 Manifest 被拒绝 | 按稳定 error code 修复 |
| `graph_valid` | 整体依赖图是否合法 | 必须为 true |

同步允许部分结果，因此不能只依赖 HTTP 200；`rejected` 非空即视为本次发布失败。

## 5. 触发与查询

### 5.1 手工触发

```bash
curl -sS -X POST http://127.0.0.1:8084/features/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "features":[{"code":"platform.security.constant_one","version":2}],
    "security_ids":[2453,2375],
    "as_of_time":"2026-07-18T05:24:43Z",
    "data_cutoff_time":"2026-07-18T05:24:43Z",
    "market":"zh_a",
    "source_profile":"default",
    "trigger_type":"manual",
    "idempotency_key":"operator-ticket-123",
    "parameters":{"ticket":"operator-ticket-123"}
  }'
```

新 Run 返回 202；完全相同的幂等请求返回 200、`reused=true` 和原 `run_id`。`data_cutoff_time` 不得晚于 `as_of_time`。

### 5.2 查询执行证据

```bash
curl -sS 'http://127.0.0.1:8084/features/executions/{run_id}?source_profile=default'
curl -sS 'http://127.0.0.1:8085/api/v2/features/runs/{run_id}?include_subjects=true'
```

必须同时检查 Run 状态、时间、code revision、parameters、RunItems 质量计数和 RunSubjects。只看到 HTTP 成功不等于计算成功。

### 5.3 查询值

```bash
curl -sS 'http://127.0.0.1:8085/api/v2/features/values/numeric/latest?feature_code=platform.security.constant_one&security_ids=2453,2375&limit=100'
curl -sS 'http://127.0.0.1:8085/api/v2/features/values/numeric?feature_code=platform.security.constant_one&version=1&run_id={run_id}&limit=100'
```

当查询历史 Run 时必须显式提供 `version` 或 `feature_version_id`。仅提供 `feature_code` 会按最高可用 published 版本解析，可能与历史 `run_id` 不一致并返回空集。

### 5.4 查询治理状态

```bash
curl -sS 'http://127.0.0.1:8085/api/v2/features/definitions/platform.security.constant_one'
curl -sS 'http://127.0.0.1:8085/api/v2/features/lineage/platform.security.datafield_pit_probe'
curl -sS 'http://127.0.0.1:8085/api/v2/features/availability/platform.security.constant_one?source_profile=default'
```

`availability` 必须结合 definition、version、dependency、data、implementation、materialization 和 execution readiness 维度阅读，不得把单个 `status` 当作唯一依据。

## 6. 失败、重试与恢复

### 6.1 稳定错误分类

| Error code | 常见原因 | 处理 |
|---|---|---|
| `MANIFEST_CHECKSUM_CONFLICT` | Published Manifest 被修改 | 恢复原文件或发布新版本 |
| `FEATURE_DEPENDENCY_CYCLE` | Feature DAG 有环 | 修正依赖后重新 validate |
| `DATA_FIELD_CONTRACT_MISMATCH` | 精确 DataField contract 不存在 | 更新依赖到已治理 contract |
| `SOURCE_UNAVAILABLE` | PhoenixA 或数据源不可用 | 恢复依赖后创建 retry Run |
| `DATA_CUTOFF_VIOLATION` | 输入可用时间晚于 cutoff | 修复 provider；不得放宽 cutoff |
| `OUTPUT_SCHEMA_INVALID` | 输出数量或类型不合约 | 修复插件并发布新版本 |
| `VALUE_WRITE_CONFLICT` | 同一主键内容不同 | 停止重试并调查非确定性 |
| `RUN_STATE_CONFLICT` | 状态机 expected_status 已变化 | 重新读取 Run，禁止盲目覆盖 |

### 6.2 Retry

Retry 不是修改原 Run。重新提交 compute 时设置：

```json
{
  "retry_of_run_id": "failed-run-uuid",
  "force": true,
  "idempotency_key": "operator-ticket-123-attempt-2"
}
```

新 Run 保留 `retry_of_run_id`，原失败 Run 和错误证据不变。成功 Run 默认应被幂等复用；只有明确需要独立重算时才使用 `force=true`。

### 6.3 Stale Run

Artemis 启动时会按配置自动 reconcile，也可手工执行：

```bash
curl -sS -X POST 'http://127.0.0.1:8084/features/maintenance/reconcile-stale?source_profile=default'
```

PhoenixA 内部接口需要明确 cutoff：

```bash
curl -sS -X POST http://127.0.0.1:8085/api/v2/features/runs:reconcile-stale \
  -H 'Content-Type: application/json' \
  -d '{"stale_before":"2026-07-18T04:00:00Z","producer_service":"artemis"}'
```

操作前先查询 active Run 和 heartbeat；reconcile 会把过期 active Run 及其 active items 原子标为 aborted/failed，不能撤销。

## 7. Backfill

Backfill 由 PhoenixA 冻结日期展开和 universe request。创建后通过 Artemis 或调度器执行各子 Run。

- `POST /api/v2/features/backfills` 创建；
- `GET /api/v2/features/backfills/{backfill_id}` 查看进度；
- `POST /api/v2/features/backfills/{backfill_id}:retry-failed` 只重试失败日期；
- `POST /api/v2/features/backfills/{backfill_id}:cancel` 取消未终态子 Run。

同一 backfill 日期和 attempt 受唯一约束保护。禁止通过直接 SQL 绕过 retry 关系。

## 8. 容量与清理

只读容量采样：

```bash
cd /home/machine/projects/chaos/app/projects/phoenixA
python scripts/benchmark_feature_platform.py \
  --base-url http://127.0.0.1:18085 \
  --run-id {succeeded-v2-run-id} \
  --security-ids 2453,2375 \
  --requests 1000 \
  --concurrency 16 \
  --report-json /tmp/feature-platform-benchmark.json
```

容量检查同时关注错误率、整体 p95/p99、lineage、latest values 和 run detail。不能只报告 RPS。

Run 和 Value 是审计证据，生产环境不得手工删除。开发调试需要重建时，应停写、备份必要证据，然后按 migration 从空 schema 重建；不要只删除 Value 而保留 succeeded Run。生产保留策略和 Timescale chunk 压缩/归档必须另行评审。

## 9. 安全边界

当前 Phase 5 安全审查结论：

- Manifest 与 runtime parameters 已拒绝敏感 key；
- Published Version、Value 和 security identity 有数据库约束；
- Run/Item 状态转换使用 expected status；
- Feature 写接口当前没有应用层身份认证；
- Artemis CORS 当前允许任意 origin；
- 部分 home/dev 配置仍含明文基础设施或 SDK 凭证。

因此平台可在受信开发网络内解锁财务因子开发，但不能直接暴露到公网或不受信生产网络。生产发布前必须完成：

1. 在网关或服务层为 registry、run、value、backfill 和 compute 写接口增加服务身份认证与授权。
2. 将数据库、Redis 和 SDK 凭证迁移到 secret manager 或环境注入，并从可分发配置中移除。
3. 把 CORS origin 收敛到明确的 Cthulhu 域名。
4. 为写操作补充操作者身份、请求来源和审计日志保留策略。
5. 完成 TimescaleDB、`warm_storage`、备份恢复和容量保留策略的生产演练。

## 10. 发布检查表

- PhoenixA `go test ./...` 和 `go vet ./...` 通过；
- Artemis Feature Platform 定向测试通过；
- OpenAPI 路由一致性脚本通过；
- managed acceptance 包含 PIT 与重启 Gate 并通过；
- benchmark 零错误且延迟不超过本次环境基线的约定阈值；
- normal service 已部署当前二进制并重启；
- Cthulhu 指向当前 PhoenixA/Artemis；
- 生产安全前置项逐项签字；
- 变更由维护者手工提交并记录版本。
