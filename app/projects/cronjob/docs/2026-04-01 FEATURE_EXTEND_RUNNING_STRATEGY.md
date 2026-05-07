# Cronjob / Artemis 长期运行策略任务扩展设计方案

## 0. 文档目标

本文档讨论当前 `cronjob -> Artemis` 任务执行协议的扩展方向，用于支持：

- 长期运行的策略模拟任务；
- 启动后持续运行、持续汇报状态；
- 不以一次性的异步回调作为唯一完成语义；
- 允许由 cronjob 发起人工/调度终止。

本文档是 `app/projects/artemis/docs/2026-04-01 FEATURE_APPLY_TASK_ORCHESTRATION_IN_BACKTRADING.md` 的配套文档，重点解决**运行模型**问题，而不是 backtrader 本身如何做 feed / strategy / analyzer 设计。

> 本文档只做设计，不修改代码。

---

## 1. 问题定义：为什么当前模型不够

### 1.1 当前模型适合什么

从现有 Artemis 代码看：

- `TaskMode` 目前只有 `SYNC / ASYNC`；
- `TaskEngine.run()` 中的 `ASYNC` 本质上是进程内后台线程；
- `CronjobClient` 主要提供：
  - `progress()`
  - `finalize_success()`
  - `finalize_failed()`
- 当前回调模型默认任务最终会结束，并且有明确的一次性终态 callback。

这个模型非常适合：

- bounded 的历史回测；
- ETL 类任务；
- 一次性采集 / 计算任务；
- 有明确结束边界的异步任务。

### 1.2 当前模型不适合什么

它不适合以下场景：

- 启动后可能运行数小时、数天甚至长期存在的策略模拟任务；
- 任务执行期间需要**持续汇报运行中状态**，而不是只在结束时 callback；
- 任务需要被外部系统主动终止；
- 任务需要 heartbeat，用来区分“正在运行”与“进程已丢失”；
- 任务的 progress 不是简单的 `current / total` 进度条，而是连续运营型状态。

### 1.3 这次要解决的核心诉求

这次要支持的是：

- 某个策略模拟任务一旦启动；
- 默认持续运行；
- 期间不断向 cronjob 报告状态；
- 除非人工停止或调度策略要求停止，否则不自动结束；
- 停止时进行一次终态 finalize。

---

## 2. 设计原则

### 2.1 原则一：新增的是“运行语义”，不是仅新增一个 callback 类型

长期运行任务不是“ASYNC 换个名字”。

它改变的是：

- 任务生命周期；
- 调度责任边界；
- progress 语义；
- 终止控制方式；
- finalize 的时机；
- 运行中状态的可观测性。

### 2.2 原则二：`LONGRUN` 应该是通用执行类型，不只服务 backtrader

虽然这次需求来自策略模拟，但设计上建议不要命名成只服务交易领域的 `LIVE`。

更推荐：

- `LONGRUN`

理由：

- 语义更通用；
- 后续日志 tail、watcher、stream consumer 等任务也可以复用；
- 业务模式是否“live”可以放在 task body 的 `mode` 或 `run_kind` 里表达。

### 2.3 原则三：终态仍要保持明确，只是运行中变长

长期运行不代表没有终态。

仍然需要明确区分：

- 正常结束；
- 失败结束；
- 人工终止；
- 调度终止；
- 进程失联。

### 2.4 原则四：尽量不破坏现有 SYNC / ASYNC 任务

扩展应满足：

- 现有 `SYNC / ASYNC` 行为保持不变；
- bounded task 不必为了 long-run 改写执行逻辑；
- long-run 相关能力对普通任务是“可选扩展”，不是强制改造。

---

## 3. 推荐的执行类型扩展

### 3.1 建议新增 `LONGRUN`

推荐把当前：

- `SYNC`
- `ASYNC`

扩展为：

- `SYNC`
- `ASYNC`
- `LONGRUN`

### 3.2 为什么不建议直接叫 `LIVE`

`LIVE` 会让语义过度绑定到交易场景，而这次真正新增的是：

- 长期运行；
- 需要心跳；
- 需要外部 stop；
- 需要非终态进度汇报。

这些能力本身是基础设施能力，不应只属于策略系统。

### 3.3 `LONGRUN` 与 `ASYNC` 的差异

| 维度 | `ASYNC` | `LONGRUN` |
|---|---|---|
| 预期执行时长 | 一般较短 | 可长期持续 |
| 进度语义 | `current / total` 为主 | heartbeat + snapshot + progress |
| 终态 callback | 尽快到来 | 可能很久以后才到来 |
| 外部 stop | 非核心诉求 | 核心能力 |
| 丢失检测 | 非核心 | 核心能力 |
| checkpoint | 可无 | 建议有 |

---

## 4. 生命周期与状态模型

### 4.1 不建议一开始大改 `TaskStatus`

当前 `TaskStatus` 有：

- `PENDING`
- `RUNNING`
- `SUCCESS`
- `FAILED`
- `CANCELED`
- `SKIPPED`

这里不建议为了 long-run 立刻把所有中间态都塞进 `TaskStatus`，否则会影响现有 bounded task 的稳定性。

### 4.2 建议新增“运行控制状态”而不是污染终态状态枚举

更推荐的做法是：

- `TaskStatus` 继续负责**终态与主状态**；
- 额外增加一个 long-run 专用的 `run_lifecycle_state` 或 `control_state`。

建议状态：

| 状态 | 含义 |
|---|---|
| `ACCEPTED` | cronjob 已接受，等待 Artemis 真正启动 |
| `RUNNING` | 正在运行 |
| `DEGRADED` | 仍在运行，但有异常或数据源退化 |
| `STOP_REQUESTED` | cronjob 或操作员发起停止请求 |
| `STOPPING` | Artemis 已收到停止请求，正在优雅收尾 |
| `LOST_HEARTBEAT` | cronjob 长时间未收到 heartbeat |
| `FINISHED` | 已终止，等待或已经 finalize |

终态仍然可落在：

- `SUCCESS`
- `FAILED`
- `CANCELED`

### 4.3 终态建议语义

#### `SUCCESS`

适合：

- 到达预设 stop policy；
- 正常关停；
- 完整完成预期会话。

#### `FAILED`

适合：

- 策略执行异常；
- 数据源无法恢复；
- 内部运行错误；
- 无法完成必要的终态持久化。

#### `CANCELED`

适合：

- 操作员手动终止；
- cronjob 主动发起 stop；
- 上层策略要求提前中止。

---

## 5. Progress、Heartbeat 与 Snapshot 的语义拆分

这是长期运行任务里最关键的协议设计点。

### 5.1 不建议继续只用 `current / total`

当前 `progress(current, total, message)` 对有边界任务是够用的，但对 long-run 不够。

长期运行任务更需要以下三类上报：

### 5.2 Heartbeat

用于表达：

- 任务实例还活着；
- 主循环仍在推进；
- 即使没有新业务进展，也需要刷新 liveness。

建议字段：

- `run_id`
- `timestamp`
- `state`
- `message`
- `worker_identity`（可选）
- `last_bar_time`（业务任务可选）

### 5.3 Progress Snapshot

用于表达：

- 当前运行到了哪里；
- 最近处理了多少数据；
- 当前关键业务指标是什么。

建议字段：

- `run_id`
- `state`
- `summary_metrics`
- `stats`
- `checkpoint_seq`
- `message`

对策略模拟类任务，snapshot 可以包含：

- `bars_processed`
- `latest_equity`
- `open_positions`
- `signal_count`
- `order_count`
- `last_bar_timestamp`

### 5.4 Finalize

用于表达：

- 任务已经结束；
- 给出唯一终态；
- 给出最终错误或成功信息；
- 标识不再期待后续 heartbeat。

也就是说：

- heartbeat 是运行中语义；
- snapshot 是运行中观测语义；
- finalize 是终态语义。

三者不要混用。

---

## 6. Cronjob 需要扩展的能力

### 6.1 run model 扩展

cronjob 需要知道某个 run 是否为 `LONGRUN`，并据此采用不同监督方式：

- `ASYNC`：等待最终 callback；
- `LONGRUN`：等待 heartbeat + snapshot，最终再等 finalize。

### 6.2 Heartbeat 接收能力

cronjob 需要支持专门的运行中心语义，而不只是保存一条 progress message。

建议至少具备：

- 记录最后一次 heartbeat 时间；
- 记录最近一次 snapshot；
- 判断是否 heartbeat timeout；
- 区分 `RUNNING / DEGRADED / STOP_REQUESTED / STOPPING`。

### 6.3 Stop 控制能力

cronjob 需要能对长期运行任务发起停止，而不只是“等待回调”。

建议最小能力：

- 操作员或定时器标记某个 run 为 `STOP_REQUESTED`；
- Artemis 能查询到这一状态；
- Artemis 进入优雅收尾；
- 完成后发送 finalize。

### 6.4 Lost heartbeat 识别能力

cronjob 需要具备：

- 心跳超时阈值；
- 发现超时后把 run 标记为 `LOST_HEARTBEAT` 或 `DEGRADED`；
- 支持人工介入处理。

### 6.5 查询能力

对于 long-run，cronjob 最好有一个简单读模型：

- 当前状态；
- 最近 heartbeat；
- 最近 snapshot；
- stop request 是否已发起；
- 是否已经 finalize。

---

## 7. Artemis 需要扩展的能力

### 7.1 `TaskMode` 扩展

Artemis 需要新增 `TaskMode.LONGRUN`。

### 7.2 `TaskEngine` 执行策略扩展

当前 `TaskEngine.run()` 中的 `ASYNC` 是进程内线程，这对真正长期运行任务并不理想。

至少要在设计上承认：

- 长期运行任务与普通异步任务的监督语义不同；
- 最终可能需要专门的 long-run runner / supervisor；
- 不能长期依赖“HTTP 请求进程里开一个 daemon thread”作为正式交付方案。

### 7.3 Stop token / control polling 能力

Artemis 需要能在任务运行过程中感知 stop 请求。

建议方式优先级：

#### 方案 A：Artemis 主动向 cronjob 轮询 control state（推荐）

优点：

- 与当前“Artemis 作为任务执行方”边界一致；
- 避免 cronjob 反向直接控制 Artemis 运行线程；
- 更容易做幂等。

#### 方案 B：Cronjob 直接推送 stop 指令

可做，但会增加 Artemis 暴露控制接口与身份校验复杂度。

因此第一版更推荐 **Artemis 轮询 control state**。

### 7.4 Checkpoint / snapshot 能力

长期运行任务最好支持：

- 周期性产出 checkpoint；
- 周期性上报 snapshot 给 cronjob；
- 可选同步写 PhoenixA 中间结果。

### 7.5 Finalize once 能力

Artemis 必须保证：

- 一个 long-run 只 finalize 一次；
- stop 后不会继续 heartbeat；
- finalize 前尽量写 terminal snapshot；
- finalize 失败时有重试策略。

---

## 8. 推荐的控制面协议

以下是推荐的最小控制面，不要求第一版完全实现，但建议朝这个方向设计。

### 8.1 启动

cronjob 下发：

- `task_code`
- `exec_type = LONGRUN`
- `run_id`
- `task_body`

Artemis 返回：

- `accepted = true`
- `run_id`
- `exec_type = LONGRUN`

### 8.2 运行中上报

建议区分两个接口或两种消息类型：

- `heartbeat`
- `snapshot`

即使第一版仍复用一个 progress endpoint，也建议 payload 带上 `event_type`：

- `event_type = heartbeat`
- `event_type = snapshot`

### 8.3 控制查询

建议 Artemis 定时查询：

- `GET /api/v1/runs/{run_id}/control`

返回示意：

```json
{
  "run_id": 10002,
  "desired_state": "RUNNING",
  "stop_requested": false,
  "stop_reason": ""
}
```

当 cronjob 希望终止时：

```json
{
  "run_id": 10002,
  "desired_state": "STOP_REQUESTED",
  "stop_requested": true,
  "stop_reason": "manual_stop"
}
```

### 8.4 终态 finalize

仍使用一次性 finalize 语义，但 payload 应更丰富：

- `result`
- `terminal_status`
- `stop_reason`
- `summary`
- `error_message`
- `ended_at`

---

## 9. 终止语义设计

### 9.1 人工终止

操作员在 cronjob 标记：

- `STOP_REQUESTED`

Artemis 在轮询到后：

1. 停止继续读取新数据；
2. 做最后一次 checkpoint；
3. 写 terminal artifact；
4. 发送 finalize；
5. 终态建议标记为 `CANCELED`。

### 9.2 调度终止

例如：

- 到达市场收盘；
- 到达配置中的结束条件；
- 到达风控停止条件。

语义上可视为一种受控结束：

- 若属于预期 stop policy，可标 `SUCCESS`；
- 若属于外部强制停止，也可标 `CANCELED`；
- 关键是 `stop_reason` 必须清楚。

### 9.3 异常失败

若出现不可恢复错误：

- 写入最后可写的诊断信息；
- 尽量发送 failure finalize；
- 终态为 `FAILED`。

### 9.4 心跳丢失

若 cronjob 长时间未收到 heartbeat：

- 先标为 `LOST_HEARTBEAT` 或 `DEGRADED`；
- 是否自动转 `FAILED` 交由运维策略决定；
- 不建议仅靠 cronjob 超时立即伪造成功终态。

---

## 10. 对 `BaseTaskUnit` / `OrchestratorUnit` 的影响建议

### 10.1 bounded task 保持不变

不建议为了 long-run 改坏现有 bounded task 生命周期。

### 10.2 long-run worker 需要额外能力

建议 long-run worker 在 `execute()` 内部支持：

- heartbeat interval；
- checkpoint interval；
- control polling；
- graceful stop；
- terminal finalize。

### 10.3 `finalize` 的职责要更清晰

`finalize` 应继续只负责终态收口，而不是运行中报告。

运行中的持续汇报应由：

- heartbeat
- snapshot
- checkpoint

来承担。

### 10.4 Orchestrator 与长期任务的关系

`OrchestratorUnit.plan()` 依然可以用于规划 child run，但对于长期运行任务，不建议一个父任务挂大量长期 child，因为：

- 父任务生命周期会被无限拉长；
- 进度聚合意义下降；
- stop/diagnostics 管理复杂。

更推荐：

- 一个长期运行 strategy session 作为一个一级 run；
- 或者父任务只负责创建少量 long-run child，而不是大批量 fan-out。

---

## 11. 与 backtrader 实时模拟场景的映射

### 11.1 本文档解决什么

本文档解决的是：

- 如何让 cronjob 和 Artemis 能承载一个长期运行策略模拟任务；
- 如何在运行中报告状态；
- 如何停止；
- 如何终态 finalize。

### 11.2 Backtrader 文档解决什么

`FEATURE_APPLY_TASK_ORCHESTRATION_IN_BACKTRADING.md` 解决的是：

- strategy registry；
- data provider registry；
- analyzer profile；
- result schema；
- plot artifact；
- PhoenixA sink。

### 11.3 两者如何配合

组合后的语义是：

- cronjob 用 `LONGRUN` 启动一个 `BACKTRADER_CAMPAIGN` 或 `BACKTRADER_RUN`；
- Artemis 负责 backtrader 执行与 PhoenixA 落库；
- cronjob 负责监督 run 是否活着、是否被要求停止；
- 最终由 Artemis 输出唯一 finalize。

---

## 12. 推荐的最小落地路径

### 补充：当前 Phase 1 历史回测 MVP 对 cronjob 的 implementation checklist

虽然本文档主要讨论 `LONGRUN`，但当前真正要开始做的 Phase 1 其实是**bounded historical backtest**。因此 cronjob 在这一阶段不需要先做 long-run 改造，而是先完成下面这些最小对接项。

#### A. 运行模型

- [ ] Phase 1 明确继续使用现有 `ASYNC`
- [ ] 不引入 `LONGRUN`
- [ ] 不引入 heartbeat
- [ ] 不引入 stop control plane
- [ ] 保持现有“progress + finalize”语义不变

#### B. 任务定义与请求体支持

- [ ] 增加或配置可触发 `BACKTRADER_CAMPAIGN` 的任务定义
- [ ] Cronjob 传给 Artemis 的任务体要支持：
  - `mode = historical`
  - `strategy_code`
  - `symbols` 或 `universe_code`
  - `timeframe`
  - `start_date`
  - `end_date`
  - `parameter_grid` 或 `strategy_params`
- [ ] 如果 cronjob 侧已有入参 schema 校验，需要同步补齐这些字段

#### C. 运行中观测

- [ ] 继续复用当前 progress 机制显示 `children_completed / children_total`
- [ ] 不要求 cronjob 在 Phase 1 展示 analyzer 级细节
- [ ] 若已有 run detail 展示能力，优先展示：
  - `task_code`
  - `run_id`
  - `status`
  - `progress`
  - Artemis 回传的 `stats` 摘要

#### D. finalize 与失败链路

- [ ] 成功场景下能收到 Artemis 的 `finalize_success`
- [ ] 失败场景下能收到 Artemis 的 `finalize_failed`
- [ ] 父任务 fail-fast 时，cronjob 看到的终态应是父任务 failed，而不是误显示 child success
- [ ] 不因为历史回测任务耗时较长，就过早认定 run 异常失联

#### E. Phase 1 完成判据

- [ ] cronjob 可以手工或调度触发一个历史回测 campaign
- [ ] 可以看到 progress 从 `0/N` 走到 `N/N`
- [ ] 可以收到最终 callback
- [ ] 可以从 callback / stats 中定位失败原因
- [ ] 不需要等 `LONGRUN` 设计落地后，Phase 1 才能上线

### Phase 1：协议先行

先定义清楚：

- `LONGRUN` exec type
- heartbeat payload
- snapshot payload
- control state 查询
- finalize payload

### Phase 2：最小可运行 long-run

在 Artemis 支持：

- long-run task 启动
- 周期性 heartbeat
- stop polling
- graceful stop

在 cronjob 支持：

- run 状态查看
- 手动 stop
- 最近 heartbeat / snapshot 查看

### Phase 3：增强监督与恢复

后续再考虑：

- heartbeat timeout 自动判定策略；
- runner crash 恢复；
- pause / resume；
- 多实例监督；
- 更完整的审计日志。

---

## 13. 结论

针对“长期运行的实时策略模拟任务”，当前 `SYNC / ASYNC + progress + finalize` 模型是不够的。

推荐扩展方向是：

- 新增通用的 `LONGRUN` 执行类型；
- 把运行中语义拆成 `heartbeat + snapshot + finalize` 三层；
- 通过 cronjob 控制面支持 `STOP_REQUESTED`；
- 由 Artemis 轮询 control state 并进行优雅停止；
- 终态仍保持 `SUCCESS / FAILED / CANCELED`；
- bounded task 继续维持当前模型，不被 long-run 设计拖累。

这样既能满足 backtrader 实时模拟的长期运行诉求，也能把这套能力沉淀为可复用的基础设施能力。

