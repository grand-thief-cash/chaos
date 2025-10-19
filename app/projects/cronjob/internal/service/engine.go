package service

import (
	"context"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// Engine 负责基于定时表达式调度任务。
// 重新设计说明：
// 1. 增加 lastScan 记录上一次扫描时间，按窗口 (lastScan, now] 生成应触发的 due times，解决轮询间隔与任务频率不一致导致的漏触发。
// 2. shouldFire 扩展支持 "0/30"、"a-b"、"a-b/n"、单值、逗号列表、"*/n" 等常见 cron 片段（秒/分/时/日/月/周 六字段）。
// 3. 每个 due time 若已存在相同 ScheduledTime 的 Run（任意状态）则不重复创建，避免重复调度。
// 4. Overlap/并发/失败策略沿用原有语义；调度循环按时间顺序处理多个补偿触发点；补偿默认不跨越超过配置的 BatchLimit（若>0）。
// 5. ScheduledTime 使用具体触发秒 t，而不是统一当前扫描时刻，利于追踪真实计划时间。
// 6. 任务新建后仅从 max(lastScan, task.CreatedAt) 开始计算。
// 7. 保守实现：day 与 weekday 仍采用 AND 匹配（与原实现一致），后续可按需求改成 OR。

type Engine struct {
	cfg     config.SchedulerConfig
	TaskSvc *TaskService `infra:"dep:task_service"`
	RunDao  dao.RunDao   `infra:"dep:run_dao"`
	Exec    *Executor    `infra:"dep:executor"`
	*core.BaseComponent
	cancel   context.CancelFunc
	wg       sync.WaitGroup
	lastScan time.Time // 上一次 scan 成功完成时刻（秒级截断）
}

func NewEngine(cfg config.SchedulerConfig) *Engine {
	if cfg.PollInterval <= 0 {
		cfg.PollInterval = time.Second
	}
	return &Engine{cfg: cfg, BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SCHEDULER)}
}

func (e *Engine) Start(ctx context.Context) error {
	if e.IsActive() {
		return nil
	}
	if err := e.BaseComponent.Start(ctx); err != nil {
		return err
	}
	loopCtx, cancel := context.WithCancel(context.Background())
	e.cancel = cancel
	// 初始化 lastScan = 当前时间 - PollInterval，确保第一次 scan 覆盖最近一个窗口
	e.lastScan = time.Now().Add(-e.cfg.PollInterval).Truncate(time.Second)
	e.wg.Add(1)
	go func() {
		defer e.wg.Done()
		ticker := time.NewTicker(e.cfg.PollInterval)
		defer ticker.Stop()
		for {
			select {
			case <-loopCtx.Done():
				return
			case now := <-ticker.C:
				if err := e.scan(loopCtx, now); err != nil {
					log.Printf("scheduler scan err: %v", err)
				}
			}
		}
	}()
	return nil
}

func (e *Engine) Stop(ctx context.Context) error {
	if !e.IsActive() {
		return nil
	}
	if e.cancel != nil {
		e.cancel()
	}
	e.wg.Wait()
	return e.BaseComponent.Stop(ctx)
}

// scan 调度：窗口 = (e.lastScan, now] 之间所有满足 cron 的触发秒。
// 为减少负载，若窗口跨度 > 10 * PollInterval，自动截断到最近 10 * PollInterval。
// BatchLimit (>0) 限制单次任务最多补偿触发次数。
func (e *Engine) scan(ctx context.Context, now time.Time) error {
	now = now.Truncate(time.Second)
	windowStart := e.lastScan
	windowEnd := now
	maxSpan := 10 * e.cfg.PollInterval
	if windowEnd.Sub(windowStart) > maxSpan {
		windowStart = windowEnd.Add(-maxSpan)
	}
	tasks, err := e.TaskSvc.ListEnabled(ctx)
	if err != nil {
		return err
	}
	logging.Info(ctx, fmt.Sprintf("scheduler scan window (%s, %s] tasks=%d", windowStart.Format(time.RFC3339), windowEnd.Format(time.RFC3339), len(tasks)))
	for _, task := range tasks {
		// 计算用于生成 due times 的起点：任务创建时间之后
		start := windowStart
		if task.UpdatedAt.After(start) {
			start = task.UpdatedAt.Truncate(time.Second).Add(-1 * time.Second) // ensure first possible second after update considered
		}
		// 获取最近若干运行记录（用于判断重叠/失败/去重）
		recentRuns, _ := e.RunDao.ListByTask(ctx, task.ID, 50)
		// map 方便查重（ScheduledTime->exists）
		existing := make(map[int64]*model.TaskRun) // key = unix second
		var lastEffective *model.TaskRun
		for _, r := range recentRuns {
			sec := r.ScheduledTime.Unix()
			if _, ok := existing[sec]; !ok {
				existing[sec] = r
			}
			if r.Status != bizConsts.Scheduled && r.Status != bizConsts.Skipped && lastEffective == nil {
				lastEffective = r
			}
		}
		// 生成 due times
		var dueTimes []time.Time
		//在给定的时间窗口内（从 start.Add(time.Second) 到 windowEnd），
		//每隔一秒检查一次当前时间点 t 是否符合任务的 Cron 表达式（shouldFire(t, task.CronExpr)）。
		//如果符合，就将该时间点加入 dueTimes 列表。
		//如果配置了 BatchLimit，且已达到最大补偿次数，则提前终止循环。
		//这样可以确保在窗口内所有应触发的时间点都被正确记录下来，避免漏调度。
		for t := start.Add(time.Second); !t.After(windowEnd); t = t.Add(time.Second) {
			if shouldFire(t, task.CronExpr) {
				// BatchLimit 控制
				if e.cfg.BatchLimit > 0 && len(dueTimes) >= e.cfg.BatchLimit {
					break
				}
				dueTimes = append(dueTimes, t)
			}
		}
		if len(dueTimes) == 0 {
			continue
		}
		for _, fireTime := range dueTimes {
			// 已存在该 ScheduledTime 的 run（任何状态）则跳过（避免重复调度）
			if _, ok := existing[fireTime.Unix()]; ok {
				continue
			}
			// 统计是否有 pending (RUNNING/SCHEDULED)
			var hasPending bool
			var pendingRunningIDs []int64
			// 用于检查在 recentRuns（最近的任务运行记录）中，是否存在与当前 fireTime 之前或相同时间的任务实例，其状态为 Running 或 Scheduled。
			// 		如果有，则设置 hasPending = true，表示有未完成的实例。
			//		如果状态为 Running，还会把该实例的 ID 加入 pendingRunningIDs，用于后续并发控制或取消操作。
			//这样可以实现对任务并发、重叠等调度策略的判断和处理。
			for _, r := range recentRuns {
				if r.ScheduledTime.After(fireTime) { // 仅关注更早或相同时间的 pending
					continue
				}
				if r.Status == bizConsts.Running || r.Status == bizConsts.Scheduled {
					hasPending = true
					if r.Status == bizConsts.Running {
						pendingRunningIDs = append(pendingRunningIDs, r.ID)
					}
				}
			}
			ignoreConcurrency := false
			if hasPending {
				switch task.OverlapAction {
				case bizConsts.OverlapSkip:
					// 记录 skipped 占位
					run := &model.TaskRun{TaskID: task.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: nextAttempt(lastEffective, false)}
					if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
						_ = e.RunDao.MarkSkipped(ctx, run.ID)
						existing[fireTime.Unix()] = run
					}
					continue
				case bizConsts.OverlapCancelPrev:
					for _, rid := range pendingRunningIDs {
						e.Exec.CancelRun(rid)
						_ = e.RunDao.MarkCanceled(ctx, rid)
					}
				case bizConsts.OverlapParallel:
					ignoreConcurrency = true
				case bizConsts.OverlapAllow:
					// 继续后续并发判断
				}
			}
			failedPrev := lastEffective != nil && isFailureStatus(lastEffective.Status)
			attempt := 1
			if failedPrev {
				// 查找是否已存在 prev.Attempt+1 的 skipped
				var alreadySkipped bool
				if lastEffective != nil {
					for _, r := range recentRuns {
						if r.Status == bizConsts.Skipped && r.Attempt == lastEffective.Attempt+1 && r.ScheduledTime.After(lastEffective.ScheduledTime) {
							alreadySkipped = true
							break
						}
					}
				}
				switch task.FailureAction {
				case bizConsts.FailureSkip:
					if lastEffective == nil {
						attempt = 1
					} else if !alreadySkipped {
						run := &model.TaskRun{TaskID: task.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: lastEffective.Attempt + 1}
						if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
							_ = e.RunDao.MarkSkipped(ctx, run.ID)
							existing[fireTime.Unix()] = run
						}
						continue
					} else {
						attempt = lastEffective.Attempt + 2
					}
				case bizConsts.FailureRetry:
					if lastEffective != nil {
						attempt = lastEffective.Attempt + 1
					} else {
						attempt = 1
					}
				case bizConsts.FailureRunNew:
					attempt = 1
				}
			}
			// 并发上限
			if !ignoreConcurrency && task.MaxConcurrency > 0 && e.Exec.ActiveCount(task.ID) >= task.MaxConcurrency {
				switch task.ConcurrencyPolicy {
				case bizConsts.ConcurrencySkip:
					run := &model.TaskRun{TaskID: task.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: attempt}
					if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
						_ = e.RunDao.MarkSkipped(ctx, run.ID)
						existing[fireTime.Unix()] = run
						logging.Info(ctx, fmt.Sprintf("task %d skipped due to concurrency", task.ID))
					}
					continue
				case bizConsts.ConcurrencyParallel:
					// 忽略限流
				case bizConsts.ConcurrencyQueue:
					// 简化：不新建（不排队），直接丢弃
					continue
				}
			}
			// 创建调度
			run := &model.TaskRun{TaskID: task.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: attempt}
			if err := e.RunDao.CreateScheduled(ctx, run); err != nil {
				logging.Info(ctx, fmt.Sprintf("create scheduled failed task=%d time=%s err=%v", task.ID, fireTime, err))
				continue
			}
			logging.Info(ctx, fmt.Sprintf("task %d scheduled run=%d at %s attempt=%d", task.ID, run.ID, fireTime.Format(time.RFC3339), attempt))
			e.Exec.Enqueue(run)
			// 更新上下文信息
			recentRuns = append([]*model.TaskRun{run}, recentRuns...)
			existing[fireTime.Unix()] = run
			if run.Status != bizConsts.Skipped && run.Status != bizConsts.Scheduled { // always scheduled here, condition defensive
				lastEffective = run
			}
		}
	}
	// 更新 lastScan（必须在所有任务处理完后）
	e.lastScan = now
	return nil
}

func isFailureStatus(s bizConsts.RunStatus) bool {
	switch s {
	case bizConsts.Failed, bizConsts.Timeout, bizConsts.FailedTimeout, bizConsts.Canceled:
		return true
	default:
		return false
	}
}

func nextAttempt(prev *model.TaskRun, failedPrev bool) int {
	if prev == nil || !failedPrev {
		return 1
	}
	return prev.Attempt + 1
}

// shouldFire 高级 Cron 匹配：支持 *, 数值, a-b, a-b/n, */n, a/n (起始+步长), 逗号列表。
func shouldFire(t time.Time, expr string) bool {
	parts := strings.Fields(strings.TrimSpace(expr))
	if len(parts) == 5 { // 兼容 5 字段：补秒=0
		parts = append([]string{"0"}, parts...)
	}
	if len(parts) != 6 {
		return false
	}
	vals := []int{t.Second(), t.Minute(), t.Hour(), t.Day(), int(t.Month()), int(t.Weekday())}
	ranges := [][2]int{{0, 59}, {0, 59}, {0, 23}, {1, 31}, {1, 12}, {0, 6}}
	for i, field := range parts {
		if !matchField(vals[i], field, ranges[i][0], ranges[i][1]) {
			return false
		}
	}
	return true
}

func matchField(val int, expr string, min, max int) bool {
	expr = strings.TrimSpace(expr)
	if expr == "*" || expr == "?" { // 支持 ?
		return true
	}
	// 逗号列表
	for _, seg := range splitComma(expr) {
		seg = strings.TrimSpace(seg)
		if seg == "" {
			continue
		}
		if matchSegment(val, seg, min, max) {
			return true
		}
	}
	return false
}

func matchSegment(val int, seg string, min, max int) bool {
	// */n
	if strings.HasPrefix(seg, "*/") {
		step := toInt(seg[2:])
		if step <= 0 {
			return false
		}
		return (val-min)%step == 0
	}
	// a/b (起始+步长)
	if strings.Contains(seg, "/") && !strings.HasPrefix(seg, "*/") {
		parts := strings.Split(seg, "/")
		if len(parts) == 2 {
			start := toInt(parts[0])
			step := toInt(parts[1])
			if start < min || start > max || step <= 0 {
				return false
			}
			if val < start {
				return false
			}
			return (val-start)%step == 0
		}
	}
	// a-b 或 a-b/n
	if strings.Contains(seg, "-") {
		var rangePart, stepPart string
		if strings.Contains(seg, "/") { // a-b/n
			ps := strings.Split(seg, "/")
			if len(ps) != 2 {
				return false
			}
			rangePart = ps[0]
			stepPart = ps[1]
		} else {
			rangePart = seg
		}
		rg := strings.Split(rangePart, "-")
		if len(rg) != 2 {
			return false
		}
		start := toInt(rg[0])
		end := toInt(rg[1])
		if start > end || start < min || end > max {
			return false
		}
		if stepPart == "" {
			return val >= start && val <= end
		}
		step := toInt(stepPart)
		if step <= 0 {
			return false
		}
		if val < start || val > end {
			return false
		}
		return (val-start)%step == 0
	}
	// 单值
	v := toInt(seg)
	if v < min || v > max {
		return false
	}
	return v == val
}

func splitComma(s string) []string {
	var r []string
	cur := ""
	for _, c := range s {
		if c == ',' {
			if cur != "" {
				r = append(r, cur)
				cur = ""
			}
			continue
		}
		cur += string(c)
	}
	if cur != "" {
		r = append(r, cur)
	}
	return r
}

func toInt(s string) int {
	n := 0
	if s == "" {
		return -1
	}
	neg := false
	if s[0] == '+' {
		s = s[1:]
	} else if s[0] == '-' {
		neg = true
		s = s[1:]
	}
	for _, c := range s {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		} else {
			return -1
		}
	}
	if neg {
		return -1
	}
	return n
}

// Debug helper (not used currently)
