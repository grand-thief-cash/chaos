# Cron 调度策略扩展说明

本文档描述新增的运行时策略字段以及与 Misfire 策略的组合关系。

## 新增字段
- overlap_action: 当下一次触发时间到达时，上一轮仍在 RUNNING 时的处理方式。
  - ALLOW: 按原并发策略继续（默认）。
  - SKIP: 跳过本次触发，记录一个 SCHEDULED -> SKIPPED 的 run。
  - CANCEL_PREV: 取消上一轮（如果仍运行）并启动新一轮。
  - PARALLEL: 忽略并发限制（即使 concurrency_policy=SKIP/QUEUE），直接并行执行。
- failure_action: 上一次运行失败/超时/取消后本次触发的处理方式。
  - RUN_NEW: 正常新建一次运行（attempt 重置为 1，默认）。
  - SKIP: 跳过本次并记录 SKIPPED。
  - RETRY: 作为重试，attempt = 上一次 attempt + 1。

## 与并发策略的组合
- concurrency_policy=SKIP 时超出并发上限直接跳过；但 overlap_action=PARALLEL 会覆盖限制，对仅“上一轮仍在运行”情形放行。
- concurrency_policy=QUEUE 当前实现：仍直接入队（相当于排队），后续可扩展队列深度。

## 与 Misfire 策略组合
扫描间隔可能错过多个触发秒：
- FIRE_NOW: 全部补调度。
- SKIP: 只调度当前秒（错过的全部丢弃）。
- CATCH_UP_LIMITED: 只补最近 N 秒（N = catchup_limit）。
补出的每一个触发秒再逐个应用 overlap / failure / concurrency 逻辑。

## 运行状态新增
- TIMEOUT: 执行阶段请求超时（由 executor 区分 context.DeadlineExceeded）。

## 取消逻辑
- overlap_action=CANCEL_PREV 会调用 executor.CancelRun 尝试取消，在数据库层 MarkCanceled；若实际已结束则状态不会更新。

## 未来扩展
- failure_action 计划增加 BACKOFF、HALF_OPEN 等模式。
- overlap_action 计划支持最大并行重叠数限制。

## 使用方式
在创建 / 更新 Task 时设置两个字段：overlap_action、failure_action；未设置默认 ALLOW / RUN_NEW。迁移脚本 `0001_init.sql` 直接包含对应列（旧的 `0002_add_overlap_failure.sql` 已废弃为 no-op）。

---

### `scan` function execution flow

1. Get all enabled tasks (`ListEnabled`).
2. Log current scan time and task count.
3. For each task, check if it should fire (`shouldFire`).
4. Query recent task run records (`ListByTask`).
5. Check for running/scheduled instances, handle concurrency policy.
6. Find last valid execution (not SCHEDULED/SKIPPED).
7. If last failed, handle failure policy.
8. Check concurrency limit, handle concurrency policy.
9. Create scheduled record (`CreateScheduled`), enqueue for execution (`Enqueue`).




### 3. 执行阶段与超时
Executor.worker：
1. 从队列取出 run，TransitionToRunning() 设置状态 RUNNING + start_time。
2. 根据 Task.TimeoutSeconds 创建 `context.WithTimeout`。
3. 发起 HTTP 请求。
4. 根据结果：
   - 成功：MarkSuccess
   - `DeadlineExceeded`：MarkTimeout
   - 主动取消：MarkCanceled
   - 其他错误：MarkFailed
5. 清理 activePerTask 计数与 cancelMap。

### 4. Attempt 语义
- attempt=1：正常首次运行或 FailureAction=RUN_NEW 后的新轮。
- attempt>1：重试（FailureAction=RETRY）。

### 5. 并发与重叠的协同
- overlap_action=PARALLEL：仅当上一轮仍在运行时放宽并发判断（ignoreConcurrency=true）。
- concurrency_policy=SKIP：被 PARALLEL 覆盖时不再跳过。

### 6. 跳过记录
所有策略性跳过（overlap=SKIP / failure=SKIP / concurrency=SKIP）统一：
1. CreateScheduled(run)
2. MarkSkipped(run.ID)
3. 记录 end_time，便于后续审计和统计。

### 7. 取消上一轮
overlap_action=CANCEL_PREV：在发现上一轮 RUNNING 时：
- 调用 executor.CancelRun(lastRun.ID) 触发 context.Cancel()
- MarkCanceled(lastRun.ID)（如果尚未结束）。


### 9. 关键边界情况
- 任务被禁用（status=DISABLED）：ListEnabled 不返回，立即停止调度。
- TimeoutSeconds <=0：Executor 默认使用 10s 兜底。
- 多个 fireTime 在同一次 scan 中：lastRun 逐步更新，使得后续 fireTime 的 overlap/failure 判断参照最新运行。
- CANCEL_PREV 遇到上一轮其实已结束：MarkCanceled 条件不符合（状态不在 RUNNING/SCHEDULED），不会更新，安全退出。

### 10. 后续可监控指标（待扩展）
- runs_total{status}
- task_overlap_skipped_total
- task_failure_retry_total
- task_timeout_total
- concurrency_skipped_total

---
## 流程总结简图
```
[ Engine ticker ]
       |
       v
  scan window 构造 -> cron 匹配 -> misfire 过滤 -> per task fireTime 序列
       |
       v
  对每个 fireTime:
    读取 lastRun
    判断 overlap + 应用 overlap_action
    判断 failure + 应用 failure_action
    并发限制判断 (可能被 PARALLEL 覆盖)
    CreateScheduled
    (skip? MarkSkipped : Enqueue executor)
    更新 lastRun
```

---
## 示例配置
```
{
  "name": "demo-task",
  "cron_expr": "*/5 * * * * *",  // 每 5 秒
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "CANCEL_PREV",
  "failure_action": "RETRY",
  "misfire_policy": "CATCH_UP_LIMITED",
  "catchup_limit": 3,
  "timeout_seconds": 8
}
```

行为：
- 如果上一轮还在跑并到达新触发：取消上一轮后立即启动新一轮。
- 如果上一轮失败：attempt 递增（上一次 attempt+1）。
- 如果扫描延迟导致错过多次触发：最多补最近 3 次。
- 超出并发（由于 max_concurrency=1）且不是重叠场景：直接跳过（因为 concurrency_policy=SKIP）。

---
更新日期：2025-10-18
