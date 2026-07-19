# Feature Platform Phase 5 验收报告

> 验收日期：2026-07-18
>
> 基线提交：`8caf59d6adb833c58d99171729b9cd8a2fc67e12` + Phase 5 worktree
>
> 远端环境：`/home/machine/projects/chaos`
>
> 结论：受信开发网络内通过，财务因子开发解锁；公网/生产发布仍受安全和基础设施 Gate 限制

## 1. 结论摘要

| ID | 交付 | 结论 |
|---|---|---|
| FP-5.1 | 可重复 E2E acceptance | 通过 |
| FP-5.2 | PhoenixA/Artemis OpenAPI | 通过 |
| FP-5.3 | 运维手册 | 已交付 |
| FP-5.4 | FeaturePlugin 开发指南 | 已交付 |
| FP-5.5 | 当前硬件容量与查询基线 | 通过，零错误 |
| FP-5.6 | 安全检查 | 已完成，生产阻断项已记录 |
| FP-5.7 | Architecture Review | 与主设计逐项一致 |

平台已经证明 Registry -> Plan -> Compute -> Persist -> Query 主链、版本共存、PIT cutoff、质量证据、幂等和跨重启恢复。后续可以开始独立的财务因子设计与实现，但不能把 Smoke/PIT probe 当作业务因子，也不能绕过 FeatureVersion 和 DataField contract。

## 2. 验收环境

| 项目 | 值 |
|---|---|
| OS | Linux 5.15.0-122-generic x86_64 |
| CPU | 8 logical CPUs |
| Memory | 16,764,542,976 bytes |
| Python | 3.11.10 |
| PhoenixA isolated endpoint | `http://127.0.0.1:18085` |
| Artemis isolated endpoint | `http://127.0.0.1:18084` |
| Normal Cthulhu endpoint | `http://192.168.31.142:4200` |
| PhoenixA source config | `app/projects/phoenixA/config/config-home.yaml` |
| PhoenixA version | v1.38.0 |
| Artemis version | v0.47.0 |

managed acceptance 使用临时配置和隔离端口，不停止已有 8085、8084 或 4200 进程。数据库最初缺少 Feature Platform schema，本轮使用现有 `0008_feature_platform.sql` 初始化开发库后继续验收。

## 3. 自动化验收

入口：`app/projects/artemis/scripts/feature_platform_acceptance.py`。

机器可读证据：

```text
/tmp/feature-platform-phase5-acceptance.json
/tmp/feature-platform-phase5-benchmark.json
```

### 3.1 Registry 与版本

- catalog 校验 3 个 Manifest，entrypoint 可导入；
- 连续 sync 两次，V1、V2 和 PIT probe 均进入 `unchanged`，`rejected=[]`，`graph_valid=true`；
- `platform.security.constant_one@1` 和 `@2` 均为 published；
- V1 Published Manifest 人为修改后被 `MANIFEST_CHECKSUM_CONFLICT` 拒绝；
- latest 查询选择 V2，显式 `version=1 + run_id` 可以读取 V1 历史值。

### 3.2 Smoke E2E

| Feature | Run ID | Subjects | Values | 结果 |
|---|---|---:|---:|---|
| `platform.security.constant_one@1` | `847e28c3-6647-4e32-ac37-4d9a8005f98b` | 10 | 10 x 1.0 | succeeded |
| `platform.security.constant_one@2` | `fcc7c6b0-60e8-4df5-bdd9-9cc4955ed3c0` | 10 | 10 x 2.0 | succeeded |

两个请求重复提交均返回 200、`reused=true` 和原 Run ID。Run 保存 code revision、as-of、cutoff、source profile、security universe、parameters、RunItem 质量和开始/结束时间。

### 3.3 PIT E2E

PIT 场景 `phase5-20260718T055439Z`：

| 项目 | 证据 |
|---|---|
| Feature | `platform.security.datafield_pit_probe@1` |
| FeatureVersion ID | 3 |
| Run ID | `f73777e3-9faa-4b1c-8de7-4fd2c2341747` |
| Subjects/Values | 10/10 |
| Quality | valid=1, missing=9, invalid=0 |
| DataField | `amazing_data/financial_statement/income/NET_PRO_EXCL_MIN_INT_INC` |
| Contract | `2026-06-27` |
| Cutoff Gate | 所有 `source_max_available_at <= data_cutoff_time` |

负例 Run `57f9f1b5-d8d1-4815-b594-5629d0dc31ad` 人为写入晚于 cutoff 的 source availability，PhoenixA 返回 HTTP 422 和 `DATA_CUTOFF_VIOLATION`，随后 Run 被标记为预期失败证据。

### 3.4 重启持久化

acceptance 停止并重启隔离 Artemis 和 PhoenixA，重启后确认：

- V1、V2、PIT Run 与每个 Run 的 10 个 value 仍可查询；
- V1/V2 latest 和历史语义不变；
- V1/V2 原请求仍复用原 succeeded Run；
- lineage 和 availability 仍返回治理状态；
- `restart_persistence_verified=true`。

## 4. OpenAPI

PhoenixA `openapi.yaml` 升级为 v1.38.0，覆盖全部 27 条 `/api/v2/features/*` 路由，包括 registry、lifecycle、lineage、availability、run 状态机、numeric query/write 和 backfill。`verify_openapi_routes.py` 已支持 Feature scope、`PATCH` 和带 `:` 的 action path；37 条 in-scope path 与 `router_v2.go` 一致。

Artemis FastAPI metadata 升级为 v0.47.0，动态 `/openapi.json` 覆盖 compute、execution、reconcile、validate 和 sync。compute 明确记录 200 idempotent reuse、202 accepted、409 conflict 和 422 unprocessable；OpenAPI 回归测试锁定路径、请求模型和响应状态。

## 5. 容量基线

参数：1000 个只读请求、16 并发、25 warmup，轮询 definition、lineage、availability、runs、latest values、run detail 和 run values。

| 指标 | 值 |
|---|---:|
| 成功/失败 | 1000 / 0 |
| 吞吐 | 637.525 req/s |
| mean | 24.419 ms |
| p50 | 19.267 ms |
| p95 | 63.731 ms |
| p99 | 86.711 ms |
| max | 111.723 ms |

| Endpoint | p95 |
|---|---:|
| definition | 59.241 ms |
| lineage | 86.711 ms |
| availability | 61.803 ms |
| runs | 51.032 ms |
| latest values | 62.652 ms |
| run detail | 52.889 ms |
| run values | 63.731 ms |

这是当前开发硬件、小数据集和 loopback HTTP 的基线，不是生产容量承诺。生产上线前必须使用目标数据量、网络、认证网关、Timescale chunk 和真实并发重新压测。

## 6. 测试结果

| 项目 | 结果 |
|---|---|
| PhoenixA `go test ./...` | PASS |
| PhoenixA `go vet ./...` | PASS |
| OpenAPI route verifier | PASS，37 paths |
| Artemis Feature Platform targeted | 20 passed |
| Artemis full pytest | 304 passed, 3 unrelated live-service failures |

全量 Go 门禁最初发现测试仍读取已经合并回 `0008_feature_platform.sql` 的不存在 `0009_feature_platform_recovery.sql`。本轮按开发期 migration 规则清理旧引用，并把 `idx_feature_run_stale_active` 直接纳入 0008 contract 断言；修复后全绿。

Artemis 全量 pytest 的 3 个失败都在 `tests/test_financial_pipeline.py`：它们调用正在运行的旧 8085 服务，继续发送缺少 `security_id` 的旧 upsert body 或断言旧分页 envelope；不是 Phase 5 回归。该套件应迁移到当前 PhoenixA 契约并改为 managed fixture。pytest 另报告 `asyncio_mode` 插件配置和既有数据/PyTables warnings，不影响本 Gate。

Phase 4 Cthulhu 已在前一提交完成 `development-home` build、10 个 Feature Platform 定向测试、1 个布局测试和桌面/390px 渲染检查；本轮未修改 Cthulhu。

## 7. Architecture Review

| 主设计决策 | 实现核对 | 结果 |
|---|---|---|
| PhoenixA 是 Registry/Run/Value 权威 | 定义、运行和数值持久化在 PhoenixA | 一致 |
| Artemis 是执行器 | Manifest、planner、plugin、TaskEngine 经 client 落库 | 一致 |
| Cthulhu 是工作台 | 只经 API 查询和触发 | 一致 |
| 无旧 Factor/Regime 入口 | removal regression 存在，Feature API 独立 | 一致 |
| Published immutable | service + DB + E2E mutation probe | 一致 |
| Numeric immutable/idempotent | PK、advisory lock、conflict semantics | 一致 |
| PIT 使用 availability | provider、source max、DB trigger、E2E 负例 | 一致 |
| RunSubject 冻结 identity | 10 个 security_id 快照跨重启存在 | 一致 |
| DAG 与精确 DataField contract | stable planner、cycle check、lineage contract | 一致 |
| succeeded-only latest | DAO、测试、E2E 均验证 | 一致 |
| Retry 保留失败证据 | `retry_of_run_id` 创建新 Run | 一致 |
| Atlas 本轮只预留协议 | 未加入 Atlas 业务实现 | 一致 |

## 8. 安全检查

已通过：Manifest 和 runtime parameters 拒绝敏感 key；API 使用 typed/strict input；DAO 参数绑定；Published Version、Value、security identity 和 PIT cutoff 有数据库约束；状态转换使用 expected status；Run、Item、quality、error、revision 和 lineage 可审计。

生产阻断项：

1. PhoenixA Feature write routes 和 Artemis compute/sync routes 当前没有应用层认证授权。
2. Artemis 当前允许 wildcard CORS。
3. 部分 tracked home/dev config 仍含明文数据库、Redis 或 SDK 凭证。
4. 写操作尚未记录经过认证的 operator/service principal。
5. TimescaleDB、`warm_storage`、备份恢复和保留策略尚未完成生产演练。

FP-5.6 安全审查已完成，但以上问题关闭前不得公网暴露或宣称 production ready。

## 9. 已知限制

- normal 8085 在验收前是旧二进制；本轮通过隔离 18085 验证当前代码。部署后必须重启 normal PhoenixA/Artemis，Cthulhu 才能使用真实 Feature API。
- 3 个旧 financial pipeline live tests 需要迁移到 `security_id` 和当前 envelope。
- 容量基线不覆盖生产网络、网关认证或长期数据增长。
- production security、Timescale/warm storage 和保留策略属于生产发布阻断，不阻断受信环境内财务因子开发。
- 财务因子必须作为新设计迭代，不得复活已删除 Factor Engine，也不得把 PIT probe 扩展成业务实现。

## 10. 解锁决策

Phase 0 至 Phase 5 基础能力已经在受信远端开发环境闭环，允许开始下一阶段财务因子项目的设计与开发，前提是继续使用 FeatureDefinition/Version/Manifest/Plugin/Run/Value 契约，固定 DataField contract、遵守 PIT、先 Draft/review/publish，并且不把“开发解锁”解释为“生产发布批准”。
