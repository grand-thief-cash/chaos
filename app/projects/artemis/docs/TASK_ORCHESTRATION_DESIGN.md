# Artemis 任务编排系统重新设计方案

## ✅ 基于反馈的修订摘要 (Revision R1)
本次修订根据你的评论对初版方案做“最小可行”简化，保留后续扩展空间：
- 调度：所有任务的调度频率完全由外部 cronjob 决定，文档中不再假设“每日”运行。
- 可观测性：当前仅实现结构化日志（包含 run_id / child_key 等）；指标 & 链路追踪作为未来扩展，占位但不实现。
- 弹性控制：先不实现重试、超时、部分成功；任何子任务失败 → 立即终止父任务（fail-fast）；不记录 PARTIAL 状态。
- 并发 & 分块：暂不实现；父任务的子任务串行顺序执行；子任务内部也顺序处理。
- 子任务产出：数据直接 sink，不向父任务返回大量数据；父任务只关心每个子任务是否成功及少量统计（可选）。
- 运行记录：不落库。暂时仅：内存轻量对象 + 日志输出；不提供查询状态 API（移除 GET /tasks/run/{run_id}）。
- API：仅保留触发执行的 POST；支持 SYNC 和简单的 ASYNC（异步只是后台线程 + 首次响应 accepted）。进度上报依赖已存在的 callback 机制或日志；不再设计轮询查询。
- 状态枚举：缩减为 PENDING / RUNNING / SUCCESS / FAILED。
- 配置文件拆分：新增 `task.yaml` 用于任务业务配置；`config.yaml` 保留系统级配置。`task.yaml` 中不配置 source/sink，它们在任务代码中固定。`task.yaml` 重点解决“参数组合 → 配置变体”匹配；调用参数必须能匹配一个配置项，无法匹配则报错。
- 去除：并发控制、ThreadPoolExecutor、chunk_size、rate_limit、retry/backoff、部分失败聚合等章节的实现性描述；改为未来路线图说明。

---

## 1. 现状与目标（更新）
本阶段目标：建立一个结构清晰、可扩展但极简的“任务生命周期 + 父子任务编排”骨架，支持：
1. 外部 cronjob 触发不同任务；参数决定执行变体。
2. 父任务可扇出一系列子任务顺序执行；子任务失败 → 父任务立即失败。
3. 生命周期 8 阶段规范化，便于后续增强。
4. 日志充分记录（进入/退出阶段、参数、耗时、失败原因）。
5. 运行结果通过首次响应 + 可选 callback（已有机制）反馈，不做状态查询接口。

---

## 2. 精简后的架构图（顺序执行版）
```
┌──────────────┐   POST /tasks/{task_code}/run   ┌──────────────┐
│  CronJob     │ ───────────────────────────────▶ │  HTTP Gateway │
└──────────────┘                                   └──────┬───────┘
                                                           │
                                                           ▼
                                                    ┌──────────────┐
                                                    │ Task Engine  │
                                                    └──────┬───────┘
                                                           │
                                                           ▼
                                                    ┌──────────────┐
                                                    │ Task Runner  │
                                                    │ - 顺序调用   │
                                                    └──────┬───────┘
                                        ┌──────────────────┴──────────────────┐
                                        ▼                                     ▼
                                 ┌──────────────┐                     ┌──────────────┐
                                 │  BaseTask    │                     │ ParentTask    │
                                 │ (简单任务)   │                     │ fan_out()     │
                                 └──────┬───────┘                     └──────┬───────┘
                                        │                                     │
                                        │                                     ▼
                                        │                              ┌──────────────┐
                                        │                              │  ChildTask   │
                                        │                              │ (顺序执行)   │
                                        │                              └──────────────┘
                                        ▼
                               ┌────────────────────────┐
                               │ Sources / Sinks (代码) │
                               └────────────────────────┘
```

---

## 3. 运行状态 & 日志（最小实现）
### 3.1 状态枚举
```
RunStatus = { PENDING, RUNNING, SUCCESS, FAILED }
```
不再使用 PARTIAL / TIMEOUT。

### 3.2 轻量 TaskRun / ChildRun（仅内存 + 日志）
```python
class TaskRun:
    run_id: str
    task_code: str
    status: str  # PENDING|RUNNING|SUCCESS|FAILED
    incoming_params: dict
    resolved_params: dict
    start_ts: float
    end_ts: float | None
    error: str | None
    children_total: int
    children_completed: int
```
```python
class ChildRun:
    child_id: str
    parent_run_id: str
    key: str         # e.g. 股票代码
    status: str
    start_ts: float
    end_ts: float | None
    error: str | None
```
仅在内存中维护期间态（可选），核心是结构化日志：
- 进入任务：`{"event":"task_start","run_id":...,"task_code":...}`
- 生命周期阶段：`{"event":"phase_enter","phase":"execute"}` / `phase_exit`
- 子任务开始/结束：`child_start` / `child_success` / `child_failure`
- 失败：`{"event":"task_failed","error":...}`
- 成功：`task_success`（包含耗时）

### 3.3 不提供查询接口
移除 `GET /tasks/run/{run_id}`；cronjob 获取结果靠：
- SYNC：直接响应
- ASYNC：初始响应 + callback（如果使用）+ 查看日志

---

## 4. 生命周期（保持不变）
仍维持 8 阶段（加 sink），但实现强调顺序 + 简单：
1. parameter_check
2. load_task_config（从 task.yaml 选出匹配变体）
3. load_dynamic_parameters
4. merge_parameters
5. before_execute
6. execute
7. post_process
8. sink
失败点：任一阶段抛异常 → 记录日志 → 状态 FAILED → 停止后续阶段。

---

## 5. 父任务与子任务（顺序版）
### 5.1 fan_out 简化
`fan_out()` 返回一个列表：`[{"key": "000001", "params": {...}}, ...]`
### 5.2 执行策略
```
for spec in fan_out_list:
    create ChildRun (log child_start)
    try:
        执行子任务生命周期（与 BaseTask 相同简化版）
        log child_success
    except Exception:
        log child_failure
        标记父任务 FAILED 并立即中断循环
        break
```
### 5.3 父任务最终结果
- 成功：所有子任务 success
- 失败：任一子任务失败（fail-fast）

### 5.4 不做聚合统计（可选保留简单计数）
父任务响应中仅：成功/失败 + 子任务数量。

---

## 6. 配置体系（task.yaml）
### 6.1 文件拆分
- `config.yaml`：系统级（日志级别、OTel 开关等）
- `task.yaml`：任务业务配置 + 参数组合映射

### 6.2 示例 `task.yaml`
```yaml
tasks:
  stock_history_pull:
    variants:
      - match:
          freq: "daily"
          adjust: "front"    # 前复权
        config:
          date_range_days: 30
          allow_empty: false
      - match:
          freq: "weekly"
          adjust: "none"     # 不复权
        config:
          date_range_days: 180
          allow_empty: true
  stock_snapshot:
    variants:
      - match:
          snapshot_type: "full"
        config:
          fields: ["open","high","low","close","volume"]
```
### 6.3 匹配逻辑
1. `incoming_params` 中的键值必须与某个 `variant.match` 全量一致（或满足包含规则）。
2. 如果匹配结果多于1个 → 报错（歧义）。
3. 如果没有匹配 → 报错（配置不存在）。
4. 选中的 `config` 合并进生命周期参数（在 merge_parameters 阶段）。

### 6.4 不在 `task.yaml` 中出现的内容
- source/sink 类型、连接信息、写入表等 → 固定在任务代码中，避免频繁变更。

---

## 7. API（最小版）
### 7.1 触发任务
`POST /tasks/{task_code}/run`
```json
{
  "meta": { "exec_type": "SYNC" },
  "body": { "freq": "daily", "adjust": "front" }
}
```
### 7.2 响应（SYNC）
```json
{ "task_code": "stock_history_pull", "status": "SUCCESS", "run_id": "uuid-1", "children_total": 120 }
```
### 7.3 响应（ASYNC）
```json
{ "task_code": "stock_history_pull", "accepted": true, "run_id": "uuid-2" }
```
> 不提供状态查询；若需要回调则由 callback 客户端完成（已有）。

---

## 8. 日志规范（关键）
| 事件名 | 示例字段 |
|--------|---------|
| task_start | task_code, run_id, incoming_params |
| phase_enter | run_id, phase |
| phase_exit | run_id, phase, duration_ms |
| child_start | run_id, child_id, key |
| child_success | child_id, duration_ms |
| child_failure | child_id, error |
| task_failed | run_id, error, failed_phase |
| task_success | run_id, total_duration_ms, children_total |

使用统一 logger：`get_logger(task_code)`，增强上下文：`extra={'run_id':..., 'child_id':...}`。

---

## 9. 失败处理（简化）
- 不重试；异常直接失败。
- 父任务遇子任务失败立即停止后续子任务。
- 手动排查：通过日志定位失败阶段与参数。

---

## 10. 路线图（重排）
### Phase 0（当前实现）
- BaseTask / ParentTask / ChildTask 抽象（顺序）
- 生命周期钩子（无重试）
- task.yaml 解析 + 变体匹配
- 简单 TaskEngine & Runner（同步/后台线程）
- 结构化日志

### Phase 1（可选增强）
- 内存 run registry（可临时查询）
- callback 完整状态回传

### Phase 2（扩展）
- 持久化 RunStore（DB）
- GET 状态查询 API
- 指标采集（items, durations）

### Phase 3（高级）
- 并发执行（ThreadPool）
- 分块/批处理（chunking）
- 重试/指数退避/超时
- 部分成功（PARTIAL）策略

### Phase 4（演进）
- DAG / 多层任务
- 分布式执行（队列/worker）
- 熔断 / 速率限制 / 缓存

---

## 11. 示例代码（伪代码更新）
```python
class StockHistoryParentTask(ParentTask):
    def fan_out(self, ctx):
        symbols = self._load_active_symbols()
        specs = []
        for s in symbols:
            specs.append({
                'key': s,
                'params': {
                    'symbol': s,
                    'start_date': self._compute_start_date(s, ctx.resolved_params),
                    'end_date': ctx.resolved_params.get('date')
                }
            })
        return specs

    def execute(self, ctx):
        # 父任务本身可能执行轻量准备逻辑（比如加载股票列表）
        return {'symbols_count': len(self.fan_out(ctx))}
```
```python
class StockHistoryChildTask(BaseTask):
    def execute(self, ctx):
        symbol = ctx.resolved_params['symbol']
        data = self.source_fetch(symbol, ctx.resolved_params['start_date'], ctx.resolved_params['end_date'])
        return data

    def sink(self, ctx, processed):
        # 直接写入，无需返回给父任务
        self.write_to_db(processed)
```

---

## 12. 对比初版删减点
| 初版元素 | 修订后状态 |
|----------|------------|
| ThreadPool 并发 | 移除（未来 Phase 3） |
| 重试 / 超时 / 部分成功 | 移除（未来 Phase 3） |
| 运行状态查询 API | 移除（未来 Phase 2） |
| 指标落地 | 仅预留，暂不实现 |
| source/sink 动态配置 | 固定在代码，不在 task.yaml |
| chunking 分块 | 移除（未来 Phase 3） |

---

## 13. 最终简化版交付预期
实现后你将获得：
- 一个统一的任务抽象（简单任务 & 父任务 & 子任务）
- 清晰的生命周期执行顺序
- 可通过 task.yaml 精确匹配参数组合
- 在日志中可完整跟踪整个任务与每个子任务
- 简单可靠的失败处理（任一失败即停止）

---

（以下为原始设计未修订部分，供参考，如与上述修订冲突，以“Revision R1”内容为准）

