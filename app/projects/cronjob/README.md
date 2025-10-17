# CronJob 服务设计方案

> 状态：Draft (待评审)  
> 目标：提供一个可配置、可扩展、支持同步/异步 & 回调的内部 HTTP 定时任务调度服务。

## 变更记录
- v0.2 (基于评审反馈):
  - 支持默认秒级 Cron（6 字段：`sec min hour dom mon dow`），分钟级可写 5 字段自动前置 `0`。
  - 回调无需签名；支持基于 `callback_token`（推荐）或基于 `task_id + run_id` 的回调方式（备选）。
  - 手动触发等同正常一次调度运行，受并发限制；若已达并发限制直接失败返回 `CONCURRENCY_LIMIT`。
  - 取消 body/response 截断与最大长度限制相关描述；数据库字段保留完整内容（注意潜在膨胀风险后续再治理）。
  - 移除评审关注点里与重跑、截断相关条目。

---
## 1. 背景与目标
在内部系统中存在大量需要周期性调用下游服务（API）的需求

本项目提供统一的 HTTP 任务调度平台：
- 通过 Web API 创建/管理定时任务
- 支持同步（一次请求完成）与异步（外部服务稍后回调）两类执行模式
- 持久化任务与执行记录（MySQL）
- 支持重试、并发控制、超时、回调校验
- 为后续扩展分布式调度、任务依赖、告警等奠定基础

---
## 2. 术语定义
| 术语 | 说明 |
|------|--------------------------------------------|
| 任务 (Task) | 用户配置的调度条目（含 URL、Cron、执行方式等） |
| 调度 (Scheduling) | 按 Cron 计算下一次触发并生成运行实例 |
| 运行实例 (TaskRun) | 一次实际运行（含状态、耗时、请求/响应信息） |
| 同步任务 | 发起 HTTP 调用即等待响应并判定结果 |
| 异步任务 | 发起初始 HTTP 调用后进入 Callback Pending，等待外部系统回调结束 |
| 回调 (Callback) | 外部服务在处理完成后调用 cronjob 提供的回调接口完成闭环 |
| Misfire | 调度延迟未在期望时间执行的情况 |

---
## 3. 功能范围 (Scope)
### 3.1 核心功能
- 任务 CRUD（创建、查询、修改、启用/停用、删除）
- Cron 表达式解析：支持 6 字段（含秒）`sec min hour dom mon dow`；兼容输入 5 字段时自动补 `0` 秒
- 定时调度、触发执行
- 同步执行：直接 HTTP 请求，下游返回即可判定成功/失败
- 异步执行：初始调用传递 `callback_url` + `callback_token`（或提供 run_id 模式），待回调闭环
- 手动触发（立即执行一次，受并发限制）
- 运行实例查询 / 分页过滤
- 重试策略：最大次数 + 回退策略（固定/指数）
- 超时控制（连接/整体）
- 并发控制：单任务最大并发运行数 / 阻塞策略
- 回调 token 校验（无签名）
- 任务/运行状态机管理

### 3.2 数据持久化
- MySQL 存储任务与执行记录
- JSON 字段用于动态 headers / 模板等

### 3.3 非功能
- 初期单实例可用；设计兼容未来分布式（主节点选举 / DB 锁）
- 兼容水平扩展：调度器单主、执行多副本（基于 DB/分布式锁）

### 3.4 暂不实现
- 鉴权 / 多租户
- UI 控制台（仅 API）
- 任务依赖编排 / DSL
- 分布式一致性保障（除轻量锁外）
- 告警（预留 Hook）

---
## 4. 非功能需求
| 类别 | 目标 |
|------|------|
| 可用性 | 单实例高可靠（尽量无 Panic），未来支持 HA |
| 扩展性 | 模块化（Scheduler / Executor / Callback 解耦） |
| 性能 | 任务量千级、运行实例日万级的场景稳定；请求体和头部较小 |
| 一致性 | 状态更新幂等；重试无重复副作用（由业务 / 幂等键辅助） |
| 安全 | 内网、CSRF 风险低；回调 token 防冒用 |
| 可观测 | Metrics + 日志 + Trace ID 关联 |

---
## 5. 总体架构
```
+-------------------+        +------------------+
| REST API (HTTP)   |<------>|  Client (Ops)    |
+---------+---------+        +------------------+
          |                           External Services
          v                                     ^
+-------------------+      Execute HTTP        |
|  Service Layer    |--------------------------+
+---------+---------+                          |
          |                                    |
          v         schedule / fetch           |
+-------------------+     callback             |
|  Scheduler Core   |<-----------+             |
+---------+---------+            |             |
          |                      |callback     |
          v                      |             |
+-------------------+      +-----+---------+   |
|   Executor Pool   |      | Callback API  |<--+
+---------+---------+      +---------------+
          |
          v
+-------------------+
| Persistence (MySQL)|
+-------------------+
          |
          v
+-------------------+
| Logging / Metrics |
+-------------------+
```

分层说明：
- API 层：参数校验、DTO 转换
- Service 层：业务编排、事务、状态机
- Scheduler：计算 due 任务，生成运行实例，投递到执行队列
- Executor：工作协程池；负责 HTTP 调用、重试、更新状态
- Callback Handler：校验 token，幂等更新运行实例完成
- Repository：数据访问（任务 / 运行 / 锁）
- Infra：配置、日志、MySQL 连接、指标、追踪

---
## 6. 模块划分（Go 包建议）
```
internal/
  api/            # Handler, request/response DTO
  service/        # Use case 聚合逻辑
  scheduler/      # Cron 解析、扫描、入队、misfire 处理
  executor/       # HTTP 执行、重试策略、并发控制
  callback/       # 回调处理、token 校验
  repository/     # DAO，与 MySQL 交互
  model/          # 领域模型、状态枚举
  config/         # 配置加载 & 校验
  metrics/        # 指标注册
  logging/        # 日志封装
  idgen/          # ID / Token 生成
  lock/           # 分布式锁抽象（DB / MySQL GET_LOCK）
  util/           # 通用辅助
cmd/cronjob-server/main.go
migrations/      # SQL 迁移
```

---
## 7. 调度设计
### 7.1 Cron 支持
- 支持 6 字段（含秒）表达式；输入 5 字段自动补前导秒 0
- 当前解析器支持：`*`、单个数字、逗号分隔的多个数字、以及简单步进 `*/N`（对该字段取模为 0 即匹配）
- 暂不支持范围（如 1-10）及范围步进（如 1-10/2），后续 Phase2 考虑扩展
- 校验阶段规范化存储：内部统一存储 6 字段格式

### 7.2 调度循环
- 周期扫描策略：每 `poll_interval` 秒扫描下一段时间窗口（`ahead_seconds`）内 due 的任务
- 任务启用与禁用实时反映（可监听基于版本号的变更）
- 生成运行实例（TaskRun）并持久化，状态 = `SCHEDULED` → 投递执行队列（内存 channel）

### 7.3 Misfire 策略
任务上配置 `misfire_policy`：
- `FIRE_NOW`: 发现延迟一次立即执行
- `SKIP`: 跳过延迟点
- `CATCH_UP_LIMITED`: 追赶但限制 N 次

### 7.4 并发控制
- 每任务配置 `max_concurrency`
- 策略：`QUEUE`（排队）、`SKIP`（直接标记 SKIPPED）、`PARALLEL`（忽略限制）

### 7.5 状态机
```
ENABLED Task 定时 → (due) → TaskRun: SCHEDULED → RUNNING →
  SYNC: SUCCESS | FAILED | TIMEOUT | RETRYING
  ASYNC: CALLBACK_PENDING → (回调) → CALLBACK_SUCCESS | FAILED_TIMEOUT
  Canceled: CANCELED
```
（手动触发生成的 TaskRun 流程一致，状态初始仍为 SCHEDULED）

### 7.6 分布式演进（未来）
- 单主调度：基于 DB 锁 (`SELECT ... FOR UPDATE` / `GET_LOCK`) 保障只一实例执行扫描
- 执行层可多实例竞争 TaskRun（状态 CAS from SCHEDULED → RUNNING）

---
## 8. 数据库设计
### 8.1 表：tasks
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 任务 ID（雪花/自增） |
| name | VARCHAR(128) | 唯一名称 |
| description | VARCHAR(512) | 描述 |
| cron_expr | VARCHAR(64) | Cron 表达式（标准化为 6 字段） |
| timezone | VARCHAR(64) | 时区（默认 UTC/+08） |
| exec_type | ENUM('SYNC','ASYNC') | 执行类型 |
| http_method | VARCHAR(8) | GET/POST/PUT... |
| target_url | VARCHAR(512) | 目标 URL |
| headers_json | JSON | 额外请求头（Map） |
| body_template | TEXT | 请求体模板（可含占位符，如 {{run_id}}） |
| timeout_seconds | INT | 请求超时 |
| retry_policy_json | JSON | {max_retries,initial_delay,strategy,max_delay} |
| max_concurrency | INT | 并发上限 |
| concurrency_policy | ENUM('QUEUE','SKIP','PARALLEL') | 并发策略 |
| misfire_policy | ENUM('FIRE_NOW','SKIP','CATCH_UP_LIMITED') | Misfire 策略 |
| catchup_limit | INT | 追赶补偿最大次数 |
| callback_method | VARCHAR(8) | 回调 HTTP 方法（异步） |
| callback_timeout_sec | INT | 回调等待超时（超过则标记超时） |
| status | ENUM('ENABLED','DISABLED') | 任务是否激活 |
| version | INT | 乐观锁版本号 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| deleted | TINYINT | 逻辑删除 |

### 8.2 表：task_runs
索引：
- UNIQUE(name)
- idx_status_cron(status)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 运行 ID |
| task_id | BIGINT | 关联任务 |
| scheduled_time | DATETIME | 计划执行时间 |
| start_time | DATETIME | 实际开始 |
| end_time | DATETIME | 结束时间 |
| status | ENUM(...) | 运行状态 |
| attempt | INT | 当前尝试次数（从 1 开始） |
| request_headers | JSON | 实际发送头（合并全局） |
| request_body | MEDIUMTEXT | 实际请求体（完整存储） |
| response_code | INT | HTTP 状态码 |
| response_body | MEDIUMTEXT | 响应体（完整存储） |
| error_message | VARCHAR(1024) | 错误说明 |
| next_retry_time | DATETIME | 下次重试时间 |
| callback_token | CHAR(32) | 异步回调令牌（token 模式使用） |
| callback_deadline | DATETIME | 回调超时时间 |
| trace_id | VARCHAR(64) | 追踪 ID |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 8.3 表：async_callbacks
索引：
- idx_task_time(task_id, scheduled_time)
- idx_status(status)
- idx_next_retry(next_retry_time)
- idx_callback_token(callback_token)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | |
| task_run_id | BIGINT | 关联 run |
| received_at | DATETIME | 回调接收时间 |
| headers_json | JSON | 回调请求头保存 |
| body | MEDIUMTEXT | 回调请求体 |
| status | ENUM('RECEIVED','IGNORED') | 处理状态 |

### 8.4 表：scheduler_locks（可选）
| 字段 | 类型 | 说明 |
|------|------|------|
| lock_name | VARCHAR(64) PK |
| owner_id | VARCHAR(128) |
| expires_at | DATETIME |

---
## 9. API 设计（REST）
Base Path: `/api/v1`

### 9.1 任务管理
1. 创建任务  
POST `/api/v1/tasks`
```
{ "name":"sync_stats", "description":"统计同步", "cron_expr":"0 */5 * * *", "exec_type":"SYNC", "http_method":"POST", "target_url":"http://svc.internal/api/sync", "headers": {"Content-Type":"application/json"}, "body_template":"{\"run_id\": \"{{run_id}}\"}", "timeout_seconds":10, "retry_policy": {"max_retries":3,"initial_delay":5,"strategy":"exponential","max_delay":60}, "max_concurrency":1, "concurrency_policy":"QUEUE", "misfire_policy":"FIRE_NOW", "catchup_limit":5 }
```
响应：`{ "id": 123, "name": "sync_stats" }`

2. 获取任务列表  
GET `/api/v1/tasks?status=ENABLED&name=xxx&page=1&page_size=20`

3. 获取任务详情  
GET `/api/v1/tasks/{id}`

4. 更新任务（全量或部分）  
PUT `/api/v1/tasks/{id}`  
PATCH `/api/v1/tasks/{id}`

5. 启用 / 停用  
PATCH `/api/v1/tasks/{id}/enable`  
PATCH `/api/v1/tasks/{id}/disable`

6. 删除任务  
DELETE `/api/v1/tasks/{id}`

7. 手动触发一次（忽略 Cron）  
POST `/api/v1/tasks/{id}/trigger`  
Body: `{ "override_body": "...", "force_async": false }`
- 行为：创建一条正常 TaskRun；若当前并发已满且策略导致不能立即执行：
  - `QUEUE`: 进入排队（SCHEDULED 等待）
  - `SKIP`: 直接失败返回错误 `CONCURRENCY_LIMIT`
  - `PARALLEL`: 直接继续执行

### 9.2 运行实例
1. 查询任务的运行记录  
GET `/api/v1/tasks/{id}/runs?page=1&page_size=20&status=SUCCESS&from=...&to=...`

2. 获取单次运行详情  
GET `/api/v1/runs/{run_id}`

3. 取消运行：保留，仅对 SCHEDULED / RUNNING / CALLBACK_PENDING 可尝试（内部再评估是否放入 Phase >1）

### 9.3 异步回调
支持两种模式（任选其一，推荐 Token 模式）：
1. Token 模式（默认生成）：
   - Endpoint: `POST /api/v1/callbacks/{callback_token}`
   - Body: `{ "status":"SUCCESS"|"FAILED", "data":{...}, "error_message":"" }`
2. 标识模式（无需 token）：
   - Endpoint: `POST /api/v1/callbacks`
   - Body: `{ "task_id":123, "run_id":456, "status":"SUCCESS", "data":{...}, "error_message":"" }`
   - 需校验该 run 属于该 task 且处于 CALLBACK_PENDING

响应统一：`{ "run_id": 456, "final_status":"SUCCESS" }`

幂等规则：重复回调若 run 终态 → 200 + 当前终态；记录 async_callbacks(status=IGNORED)

### 9.4 系统接口
- 健康检查：GET `/api/v1/healthz`
- Metrics：GET `/metrics`
- 版本信息：GET `/api/v1/version`

### 9.5 错误响应规范
```
{
  "code": "INVALID_ARGUMENT",
  "message": "cron_expr invalid",
  "request_id": "trace-id"
}
```
错误码新增：`CONCURRENCY_LIMIT`

---
## 10. 执行流程描述
### 10.1 同步任务
```
Scheduler -> Create TaskRun(SCHEDULED)
Executor   -> CAS to RUNNING
Executor   -> HTTP 调用下游
  Success  -> SUCCESS
  Timeout/Error -> 根据重试策略 RETRYING / FAILED
```

### 10.2 异步任务
```
Scheduler -> TaskRun(SCHEDULED)
Executor  -> RUNNING -> 初始 HTTP (带 callback_url + callback_token)
下游回复接受 -> 状态 CALLBACK_PENDING
  等待回调：
    回调成功 -> CALLBACK_SUCCESS (Mapped to SUCCESS)
    回调失败/显式失败 -> FAILED
    超时未回调 -> CALLBACK_TIMEOUT (视为 FAILED)
```

### 10.3 回调交互示例 (ASCII 序列图)
```
ClientAdmin   Scheduler   Executor   TargetService   CallbackAPI
    |            |           |            |               |
(配置任务)        |           |            |               |
    |----------> |           |            |               |
    |            | (due)     |            |               |
    |            |---------> |            |               |
    |            |           |--HTTP Req->|               |
    |            |           |            |               |
    |            |           |<--202 Ack--|               |
    |            |           |            |               |
    |            |           |   (TaskRun=CALLBACK_PENDING)|
    |            |           |            |----Callback-->|--->(验证+更新)
    |            |           |            |               |
```

---
## 11. 重试与超时策略
- 每次执行失败（网络错误、5xx、超时） => 若 `attempt < max_retries`，计算下一重试时间：
  - fixed: `next = now + initial_delay`
  - exponential: `next = now + min(initial_delay * 2^(attempt-1), max_delay)`
- 重试调度实现：后台扫描 `task_runs` where status=RETRYING and `next_retry_time <= now`
- 超时：Executor 使用 context + http.Client timeout
- 异步回调超时：后台 goroutine 扫描 `CALLBACK_PENDING` 且 `callback_deadline < now` 标记 CALLBACK_TIMEOUT

---
## 12. 幂等与一致性
- 手动触发：不做“最近一次”合并；总是新建 run；若策略=SKIP 且并发已满 → 直接错误，不创建 run。

---
## 13. 配置设计 (YAML 示例)
```
server:
  port: 8080
  graceful_timeout: 10s
mysql:
  dsn: "user:pass@tcp(127.0.0.1:3306)/cronjob?charset=utf8mb4&parseTime=True&loc=Local"
  max_open_conns: 50
  max_idle_conns: 10
  conn_max_lifetime: 300s
scheduler:
  poll_interval: 1s        # 秒级支持：缩短扫描周期（可调）
  ahead_seconds: 30         # 窗口不宜过长，减少秒级误差
  batch_limit: 200
  enable_seconds_field: true
executor:
  worker_pool_size: 16
  request_timeout: 15s
  default_retry:
    max_retries: 0
callback:
  base_url: "http://cronjob.internal/api/v1/callbacks"
  token_ttl: 3600s
metrics:
  enabled: true
logging:
  level: info
```
（移除 body_log_max 及截断相关配置）

---
## 14. 监控指标 (Prometheus)
| 指标 | 类型 | 标签 | 说明 |
|------|------|------|------|
| cronjob_task_total | Gauge | status | 任务数量 |
| cronjob_run_total | Counter | status | 运行次数按终态 |
| cronjob_run_duration_seconds | Histogram | task_id | 执行耗时 |
| cronjob_run_retries_total | Counter | task_id | 重试次数 |
| cronjob_http_request_total | Counter | method,code | 对下游请求数 |
| cronjob_callback_pending | Gauge |  | 当前等待回调数量 |
| cronjob_scheduler_scan_latency | Histogram |  | 扫描耗时 |
| cronjob_misfire_total | Counter | task_id | misfire 次数 |

日志字段建议：`ts level trace_id task_id run_id attempt status msg err latency_ms target_url`

---
## 15. 安全（当前与未来）
- 仅 Token 模式 + 可选 task_id+run_id 模式；不做签名

未来扩展：
- API Key / JWT 鉴权
- 回调签名（HMAC + 时间戳）
- 速率限制（per IP / per task）
- IP 白名单

---
## 16. 失败与恢复
| 场景 | 恢复策略 |
|------|----------|
| 服务重启 | 未完成 RUNNING 重新判定：若无心跳记录，标记为 RETRYING or FAILED（配置） |
| DB 短暂不可用 | 指标告警；调度暂停（自适应退避） |
| 下游持续失败 | 重试直到上限；终态 FAILED；可触发告警 Hook（预留） |
| 回调未到达 | 超时扫描 -> CALLBACK_TIMEOUT |

---
## 17. 可扩展点 / 未来路线图
| 级别 | 事项 |
|------|------|
| Must Later | 分布式调度 Leader 选举（基于 etcd/Redis/ZK） |
| Must Later | 全局告警（邮件/钉钉/飞书） |
| Should | UI 控制台 / 前端仪表盘 |
| Should | 任务依赖 DAG / 条件执行 |
| Should | 支持多协议（gRPC, MQ） |
| Could | 任务模板与变量渲染引擎（Go template / Jinja2） |
| Could | SLA 统计与自动降级 |

---
## 18. 目录与代码结构（规划）
```
cmd/
  cronjob-server/
    main.go
internal/
  api/handlers.go
  api/router.go
  service/task_service.go
  scheduler/engine.go
  scheduler/cron_parser.go
  executor/executor.go
  executor/retry.go
  callback/handler.go
  repository/task_repo.go
  repository/run_repo.go
  model/task.go
  model/run.go
  config/config.go
  metrics/metrics.go
  logging/logger.go
pkg/
  (可选对外 SDK)
migrations/
  0001_init.sql
```

---
## 19. 示例执行生命周期（时序）
1. 管理员创建任务 (POST /tasks)
2. Scheduler 周期扫描 -> 计算 due -> 插入 task_runs
3. Executor 竞争获取 -> RUNNING -> 发 HTTP
4. 若 SYNC 成功 -> SUCCESS；失败 -> 重试策略
5. 若 ASYNC -> 标记 CALLBACK_PENDING -> 等回调
6. 回调成功 -> CALLBACK_SUCCESS；失败 -> FAILED
7. 指标 & 日志 & 可查询历史

---
## 20. 设计权衡
更新补充：
| 问题 | 当前方案 | 权衡 |
|------|----------|------|
| 秒级精度 | 秒级 Cron + 1s 扫描窗口 | 精度提升；高任务量下 DB 压力增大需后续优化（分片/内存索引） |
| 回调关联 | token 或 task_id+run_id | token 更安全；task_id+run_id 便捷；二选一兼容性好 |
| 并发下手动触发 | 遵循策略，SKIP 直接失败 | 行为可预期；避免绕过限流 |
| 数据体长度 | 全量存储 | 简化实现；需后续清理归档策略 |
| 重试机制 | 仅自动重试 | 简化 API；不灵活但满足当前诉求 |

---
## 21. 开发阶段划分（建议）
Phase 划分不变（按秒级实现调度）。

---
## 22. 评审关注点（更新后待确认）
- 秒级 Cron 已纳入：是否允许最小 500ms 精度（需要额外代价）？
- 是否需要立即实现取消运行（/runs/{id}/cancel）放入 Phase 1 还是延后？
- 是否保留 task_id+run_id 回调模式（若坚持最小安全面，可只留 token）？
- 是否需要运行记录清理/归档策略纳入早期（避免表膨胀）？

若上述确认无新增修改，即可进入实现 Phase 1。

## Quick Start (Phase 1)
1. 准备 MySQL 数据库并创建 `cronjob` schema：
   ```sql
   CREATE DATABASE IF NOT EXISTS cronjob DEFAULT CHARACTER SET utf8mb4;
   ```
2. 执行初始化表（手动或迁移工具）：
   ```sql
   SOURCE migrations/0001_init.sql;
   ```
3. 修改 `config.yaml` 中的 mysql.dsn。
4. 启动服务：
   ```bash
   go build -o cronjob-server ./cmd/cronjob-server
   ./cronjob-server -config=config.yaml
   ```
5. 创建任务（示例）：
   ```bash
   curl -X POST http://localhost:8080/api/v1/tasks -H "Content-Type: application/json" -d '{"name":"t1","description":"demo","cron_expr":"*/5 * * * *","exec_type":"SYNC","http_method":"GET","target_url":"https://httpbin.org/get","timeout_seconds":5}'
   ```
6. 手动触发：
   ```bash
   curl -X POST http://localhost:8080/api/v1/tasks/1/trigger
   ```
7. 查看运行：
   ```bash
   curl http://localhost:8080/api/v1/tasks/1/runs
   ```
8. 取消运行：
   ```bash
   curl -X POST http://localhost:8080/api/v1/runs/{run_id}/cancel
   ```

Phase 1 限制：
- 并发策略 QUEUE 当前实现为立即入队（无真正排队延迟机制），后续 Phase2 改进。
- 重试、异步回调、misfire 细则未完全实现。
- 秒级 cron 支持基础匹配（不含范围/步长表达式）。


phase 1 未实现：
- 异步任务与回调闭环（CALLBACK_PENDING / CALLBACK_SUCCESS 等状态链条）
- 重试策略（仅占位字段，未实现 RETRYING 扫描与指数退避）
- Misfire 策略逻辑（暂未根据 misfire_policy 做补偿/跳过）
- QUEUE 策略真实排队（目前直接入执行通道）
- 任务更新更细字段（仅演示描述与 cron 更新）
- 运行列表分页与过滤条件（仅简单 LIMIT）
- 指标、日志、追踪抽象（当前只用标准 log）
- 退出时等待 Worker 池优雅回收（只做了 context cancel，未显式 wg.Wait 完成）


# CronJob 服务 Phase 1 已实现 API 文档

> 说明：本文件严格对应当前代码已实现的能力（同步任务 / 基础调度 / 手动触发 / 取消 / 查询 / 启用停用 / 删除 / 健康 / 版本）。设计文档中提到但尚未实现的特性（异步回调、重试、misfire、分页、高级 Cron 表达式等）此处不列或注明未实现。
>
> 注意：当前返回的错误格式与设计稿不同，为 `{ "error": "CODE" }`，后续 Phase 会统一成结构化错误响应。

## 通用说明
- Base URL: `http://<host>:<port>` （默认 `http://localhost:8080`）
- 所有 API 使用 JSON；`Content-Type: application/json`（GET / 健康检查除外）
- 未实现鉴权
- 时区：内部存储 UTC，返回时间字段（若有）为数据库原值（通常 UTC）
- Cron：支持 5 或 6 字段；5 字段自动补 `0` 秒；支持 `*`、数字、逗号列表、`*/N` 步进；不支持范围 `1-5`、复杂表达式 `1-10/2` 等

## 数据模型（当前序列化字段）
### Task（列表/详情返回示例字段）
```json
{
  "ID": 1,
  "Name": "demo_task",
  "Description": "示例任务",
  "CronExpr": "0 */5 * * * *",
  "Timezone": "UTC",
  "ExecType": "SYNC",
  "HTTPMethod": "GET",
  "TargetURL": "https://httpbin.org/get",
  "HeadersJSON": "",            // 目前创建接口未接收 headers，保持空字符串
  "BodyTemplate": "",            // 同上
  "TimeoutSeconds": 5,
  "RetryPolicyJSON": "",         // 重试尚未实现
  "MaxConcurrency": 1,
  "ConcurrencyPolicy": "QUEUE",
  "MisfirePolicy": "FIRE_NOW",   // 尚未生效的策略字段
  "CatchupLimit": 0,
  "CallbackMethod": "POST",
  "CallbackTimeoutSec": 300,
  "Status": "ENABLED",
  "Version": 1,
  "CreatedAt": "2025-10-14T10:00:00Z",
  "UpdatedAt": "2025-10-14T10:00:00Z"
}
```
> 提示：当前创建接口只接受有限字段；未声明字段使用默认值。

### TaskRun（运行记录返回示例）
```json
{
  "ID": 12,
  "TaskID": 1,
  "ScheduledTime": "2025-10-14T10:05:00Z",
  "StartTime": "2025-10-14T10:05:00Z",
  "EndTime": "2025-10-14T10:05:00Z",
  "Status": "SUCCESS",           // 可能值：SCHEDULED, RUNNING, SUCCESS, FAILED, CANCELED, SKIPPED
  "Attempt": 1,
  "RequestHeaders": "",          // 未来会写入真实发送头
  "RequestBody": "",             // 未来支持 body_template 渲染
  "ResponseCode": 200,
  "ResponseBody": "{...}",
  "ErrorMessage": "",
  "NextRetryTime": null,          // 重试未实现
  "CallbackToken": "",           // 异步未实现
  "CallbackDeadline": null,
  "TraceID": "",
  "CreatedAt": "2025-10-14T10:05:00Z",
  "UpdatedAt": "2025-10-14T10:05:00Z"
}
```

---
## 1. 创建任务
POST `/api/v1/tasks`

当前可用字段：`name`, `description`, `cron_expr`, `exec_type`, `http_method`, `target_url`, `timeout_seconds`

请求示例：
```bash
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name":"demo_task",
    "description":"示例任务",
    "cron_expr":"*/30 * * * * *",   
    "exec_type":"SYNC",
    "http_method":"GET",
    "target_url":"https://httpbin.org/get",
    "timeout_seconds":5
  }'
```
成功响应：
```json
{ "id": 1, "name": "demo_task" }
```
错误（示例）：
```json
{ "error": "INVALID_ARGUMENT" }
```

说明：
- 5 字段 Cron 如 `*/5 * * * *` 会被标准化为 `0 */5 * * * *`
- 未提供的字段使用默认值：`MaxConcurrency=1`, `ConcurrencyPolicy=QUEUE`, `Status=ENABLED`

Postman 单行导入：
```bash
curl -X POST http://localhost:8080/api/v1/tasks -H "Content-Type: application/json" -d "{\"name\":\"demo_task\",\"description\":\"示例任务\",\"cron_expr\":\"*/30 * * * * *\",\"exec_type\":\"SYNC\",\"http_method\":\"GET\",\"target_url\":\"https://httpbin.org/get\",\"timeout_seconds\":5}"
```

---
## 2. 列出任务（仅 ENABLED）
GET `/api/v1/tasks`

示例：
```bash
curl http://localhost:8080/api/v1/tasks
```
响应（数组）：
```json
[
  { "ID":1, "Name":"demo_task", "CronExpr":"0 */5 * * * *", "Status":"ENABLED" }
]
```
注意：已 `DISABLED` 的任务不会出现在该列表。

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/tasks
```

---
## 3. 获取任务详情
GET `/api/v1/tasks/{id}`
```bash
curl http://localhost:8080/api/v1/tasks/1
```
成功响应：Task 对象；不存在：
```json
{ "error": "NOT_FOUND" }
```

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/tasks/1
```

---
## 4. 更新任务（部分字段）
PATCH `/api/v1/tasks/{id}`

当前实现仅处理 `description` 与 `cron_expr`（如果提供）。

示例：
```bash
curl -X PATCH http://localhost:8080/api/v1/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"description":"更新描述","cron_expr":"*/10 * * * * *"}'
```
响应：
```json
{"updated": true}
```
不存在：`{"error":"NOT_FOUND"}`

Postman 单行导入：
```bash
curl -X PATCH http://localhost:8080/api/v1/tasks/1 -H "Content-Type: application/json" -d "{\"description\":\"更新描述\",\"cron_expr\":\"*/10 * * * * *\"}"
```

---
## 5. 启用 / 停用任务
PATCH `/api/v1/tasks/{id}/enable`
PATCH `/api/v1/tasks/{id}/disable`

示例：
```bash
curl -X PATCH http://localhost:8080/api/v1/tasks/1/disable
curl -X PATCH http://localhost:8080/api/v1/tasks/1/enable
```
响应：
```json
{"status":"DISABLED"}
```
或
```json
{"status":"ENABLED"}
```

Postman 单行导入：
```bash
curl -X PATCH http://localhost:8080/api/v1/tasks/1/enable
curl -X PATCH http://localhost:8080/api/v1/tasks/1/disable
```

---
## 6. 删除任务（软删除）
DELETE `/api/v1/tasks/{id}`
```bash
curl -X DELETE http://localhost:8080/api/v1/tasks/1
```
响应：
```json
{"deleted": true}
```
> 删除后任务不再被调度，数据仍保留（deleted=1）。

Postman 单行导入：
```bash
curl -X DELETE http://localhost:8080/api/v1/tasks/1
```

---
## 7. 手动触发任务
POST `/api/v1/tasks/{id}/trigger`

请求体当前不读取，可为空。

示例：
```bash
curl -X POST http://localhost:8080/api/v1/tasks/1/trigger
```
成功：
```json
{"run_id": 42}
```
并发策略说明：
- 若任务策略 = SKIP 且当前活跃运行数 >= MaxConcurrency →
```json
{"error":"CONCURRENCY_LIMIT"}
```
- QUEUE / PARALLEL 直接进入执行（QUEUE 暂未真正排队）。

Postman 单行导入：
```bash
curl -X POST http://localhost:8080/api/v1/tasks/1/trigger
```

---
## 8. 列出任务运行记录（最近 N 条）
GET `/api/v1/tasks/{id}/runs`

说明：
- 当前固定返回最近 50 条（无分页参数）
- 包含所有状态（SCHEDULED, RUNNING, SUCCESS, FAILED, CANCELED, SKIPPED 等）

示例：
```bash
curl http://localhost:8080/api/v1/tasks/1/runs
```
响应：
```json
[
  { "ID":42, "TaskID":1, "Status":"SUCCESS", "ScheduledTime":"2025-10-14T10:05:00Z" },
  { "ID":41, "TaskID":1, "Status":"FAILED" }
]
```

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/tasks/1/runs
```

---
## 9. 获取单次运行详情
GET `/api/v1/runs/{run_id}`
```bash
curl http://localhost:8080/api/v1/runs/42
```
成功：TaskRun；不存在：
```json
{"error":"NOT_FOUND"}
```

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/runs/42
```

---
## 10. 取消运行
POST `/api/v1/runs/{run_id}/cancel`

适用状态：SCHEDULED / RUNNING（其他状态调用仍会返回 `CANCELED`，但可能已终态）

示例：
```bash
curl -X POST http://localhost:8080/api/v1/runs/42/cancel
```
响应：
```json
{"run_id":42, "status":"CANCELED"}
```
说明：
- RUNNING 状态：会触发 context 取消；若下游请求已返回或很快结束，可能仍显示 SUCCESS/FAILED；这是预期竞态。

Postman 单行导入：
```bash
curl -X POST http://localhost:8080/api/v1/runs/42/cancel
```

---
## 11. 健康检查
GET `/api/v1/healthz`
```
ok
```

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/healthz
```

---
## 12. 版本信息
GET `/api/v1/version`
```
v0.1.0-phase1
```

Postman 单行导入：
```bash
curl http://localhost:8080/api/v1/version
```

---
## 13. 错误码（当前实现）
| 错误值 | 触发场景 |
|--------|----------|
| INVALID_JSON | JSON 解析失败 |
| INVALID_ARGUMENT | 缺少必须字段 / 字段非法 |
| INVALID_ID | 路径 ID 解析失败 |
| NOT_FOUND | 任务或运行不存在 |
| CONCURRENCY_LIMIT | 手动触发受 SKIP 策略并发限制 |
| INTERNAL | 数据库等内部错误 |

返回示例：
```json
{"error":"NOT_FOUND"}
```

---
## 14. 快速验证脚本（可按需执行）
```bash
# 1. 创建任务
curl -X POST http://localhost:8080/api/v1/tasks -H 'Content-Type: application/json' -d '{"name":"t1","description":"d","cron_expr":"*/20 * * * * *","exec_type":"SYNC","http_method":"GET","target_url":"https://httpbin.org/get","timeout_seconds":5}'

# 2. 列表
curl http://localhost:8080/api/v1/tasks

# 3. 手动触发
curl -X POST http://localhost:8080/api/v1/tasks/1/trigger

# 4. 查看运行列表
curl http://localhost:8080/api/v1/tasks/1/runs

# 5. 查看运行详情（替换 run_id）
curl http://localhost:8080/api/v1/runs/1

# 6. 取消运行（若仍在运行）
curl -X POST http://localhost:8080/api/v1/runs/1/cancel

# 7. 禁用任务
curl -X PATCH http://localhost:8080/api/v1/tasks/1/disable

# 8. 启用任务
curl -X PATCH http://localhost:8080/api/v1/tasks/1/enable

# 9. 更新 Cron
curl -X PATCH http://localhost:8080/api/v1/tasks/1 -H 'Content-Type: application/json' -d '{"cron_expr":"*/10 * * * * *"}'

# 10. 删除任务
curl -X DELETE http://localhost:8080/api/v1/tasks/1
```

---
## 15. 与设计差异对照
| 设计项 | 现状 | 备注 |
|--------|------|------|
| 异步任务 & 回调 | 未实现 | Phase 2 目标 |
| 重试策略 | 未实现 | 字段占位，不生效 |
| Misfire 策略 | 未实现 | 后续添加扫描补偿逻辑 |
| QUEUE 真正排队 | 未实现 | 当前直接入执行通道 |
| 错误响应结构化 | 简化 | 仅 `{"error":"CODE"}` |
| 运行分页/过滤 | 未实现 | 固定最近 50 条 |
| Headers/BodyTemplate | 创建接口未接收 | 后续扩展 |
| 并发策略 SKIP | 支持 | 已加入手动触发 & 调度逻辑 |
| 并发策略 QUEUE | 逻辑未区分 | 后续实现排队队列 |

---
## 16. 后续测试建议
- 验证 Cron 秒级触发：使用 `*/5 * * * * *` 观察 5 秒间隔 run 生成
- 测试并发 SKIP：暂可临时手动改数据库 `max_concurrency=0`（模拟已达上限）再触发看 409
- 取消运行：对一个长时间目标（可用 `https://httpbin.org/delay/5`）触发后立即 cancel 观察状态变化

---
如需添加新的测试辅助端点或更详细输出（例如扩展运行过滤 / 统计指标），请提出需求。

---
## 数据模型

#### TaskRun 结构体字段说明
- `ID`：主键 ID，唯一标识一次运行实例。
- `TaskID`：关联的 Task ID，指向所属的定时任务。
- `ScheduledTime`：计划执行时间（UTC），由调度器分配。
- `StartTime`：实际开始时间，任务开始时记录。
- `EndTime`：实际结束时间，任务完成时记录。
- `Status`：运行状态，见 RunStatus 枚举。
- `Attempt`：当前尝试次数（含重试）。
- `RequestHeaders`：发送 HTTP 请求时的请求头（JSON 字符串）。
- `RequestBody`：发送 HTTP 请求时的请求体内容。
- `ResponseCode`：HTTP 响应码（如有）。
- `ResponseBody`：HTTP 响应体内容（如有）。
- `ErrorMessage`：错误信息（如有）。
- `NextRetryTime`：下次重试时间（如有重试计划）。
- `CallbackToken`：回调 token，用于异步任务回调识别。
- `CallbackDeadline`：回调超时时间（异步任务专用）。
- `TraceID`：链路追踪 ID（如有）。
- `CreatedAt`：创建时间。
- `UpdatedAt`：最近更新时间。

#### RunStatus 枚举类型
- `SCHEDULED`：已调度，等待执行。
- `RUNNING`：正在执行。
- `SUCCESS`：执行成功。
- `FAILED`：执行失败。
- `TIMEOUT`：执行超时。
- `RETRYING`：正在重试。
- `CALLBACK_PENDING`：等待异步回调。
- `CALLBACK_SUCCESS`：异步回调成功。
- `FAILED_TIMEOUT`：回调超时失败。
- `CANCELED`：被取消。
- `SKIPPED`：被跳过。
