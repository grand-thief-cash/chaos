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
// 去除补偿：每个 poll tick 仅检查当前时间是否触发，不再回溯补偿漏掉的时间点。
// Cron 六字段解析保留（兼容秒）。
// Overlap/并发/失败策略沿用原语义。

type Engine struct {
	cfg     config.SchedulerConfig
	TaskSvc *TaskService `infra:"dep:task_service"`
	RunDao  dao.RunDao   `infra:"dep:run_dao"`
	Exec    *Executor    `infra:"dep:executor"`
	*core.BaseComponent
	cancel context.CancelFunc
	wg     sync.WaitGroup
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

// scan：仅检测当前 tick 时间是否需要触发。
func (e *Engine) scan(ctx context.Context, now time.Time) error {
	now = now.Truncate(time.Second)
	tasks, err := e.TaskSvc.ListEnabled(ctx)
	if err != nil {
		return err
	}
	logging.Info(ctx, fmt.Sprintf("scheduler tick %s tasks=%d", now.Format(time.RFC3339), len(tasks)))
	for _, task := range tasks {
		// 是否触发
		if !shouldFire(now, task.CronExpr) {
			continue
		}
		// 最近运行记录（用于 overlap / failure / dedup）
		recentRuns, _ := e.RunDao.ListByTask(ctx, task.ID, 50)
		existing := make(map[int64]*model.TaskRun)
		var lastEffective *model.TaskRun
		for _, r := range recentRuns {
			sec := r.ScheduledTime.Unix()
			if _, ok := existing[sec]; !ok {
				existing[sec] = r
			}
			if r.Status != bizConsts.Scheduled && r.Status != bizConsts.FailureSkip && r.Status != bizConsts.ConcurrentSkip && r.Status != bizConsts.OverlapSkip && lastEffective == nil {
				lastEffective = r
			}
		}
		// 已存在当前秒调度则跳过
		if _, ok := existing[now.Unix()]; ok {
			continue
		}
		// overlap 检查（是否有之前的 pending）
		var hasPending bool
		var pendingRunningIDs []int64
		for _, r := range recentRuns {
			if r.ScheduledTime.After(now) { // 仅关注过去或当前
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
			case bizConsts.OverlapActionSkip:
				run := &model.TaskRun{TaskID: task.ID, ScheduledTime: now, Attempt: nextAttempt(lastEffective, false)}
				if err := e.RunDao.CreateSkipped(ctx, run, bizConsts.OverlapSkip); err == nil {
					logging.Info(ctx, fmt.Sprintf("task %d overlap skip", task.ID))
				}
				continue
			case bizConsts.OverlapActionCancelPrev:
				for _, rid := range pendingRunningIDs {
					e.Exec.CancelRun(rid)
				}
			case bizConsts.OverlapActionParallel:
				ignoreConcurrency = true
			case bizConsts.OverlapActionAllow:
				// fallthrough
			}
		}
		failedPrev := lastEffective != nil && isFailureStatus(lastEffective.Status)
		attempt := 1
		if failedPrev {
			var alreadySkipped bool
			if lastEffective != nil {
				for _, r := range recentRuns {
					if (r.Status == bizConsts.FailureSkip || r.Status == bizConsts.ConcurrentSkip || r.Status == bizConsts.OverlapSkip) &&
						r.Attempt == lastEffective.Attempt+1 &&
						r.ScheduledTime.After(lastEffective.ScheduledTime) {
						alreadySkipped = true
						break
					}
				}
			}
			switch task.FailureAction {
			case bizConsts.FailureActionSkip:
				if lastEffective == nil {
					attempt = 1
				} else if !alreadySkipped {
					run := &model.TaskRun{TaskID: task.ID, ScheduledTime: now, Attempt: lastEffective.Attempt + 1}
					if err := e.RunDao.CreateSkipped(ctx, run, bizConsts.FailureSkip); err == nil {
						logging.Info(ctx, fmt.Sprintf("task %d failure skip attempt=%d", task.ID, run.Attempt))
					}
					continue
				} else {
					attempt = lastEffective.Attempt + 2
				}
			case bizConsts.FailureActionRetry:
				if lastEffective != nil {
					attempt = lastEffective.Attempt + 1
				}
			case bizConsts.FailureActionRunNew:
				attempt = 1
			}
		}
		// concurrency
		if !ignoreConcurrency && task.MaxConcurrency > 0 && e.Exec.ActiveCount(task.ID) >= task.MaxConcurrency {
			switch task.ConcurrencyPolicy {
			case bizConsts.ConcurrencySkip:
				run := &model.TaskRun{TaskID: task.ID, ScheduledTime: now, Attempt: attempt}
				if err := e.RunDao.CreateSkipped(ctx, run, bizConsts.ConcurrentSkip); err == nil {
					logging.Info(ctx, fmt.Sprintf("task %d concurrency skip", task.ID))
				}
				continue
			case bizConsts.ConcurrencyParallel:
				logging.Info(ctx, fmt.Sprintf("task %d concurrency parallel policy ignore limit", task.ID))
			}
		}
		// schedule normal
		run := &model.TaskRun{TaskID: task.ID, ScheduledTime: now, Status: bizConsts.Scheduled, Attempt: attempt}
		if err := e.RunDao.CreateScheduled(ctx, run); err != nil {
			logging.Info(ctx, fmt.Sprintf("task %d create scheduled failed err=%v", task.ID, err))
			continue
		}
		logging.Info(ctx, fmt.Sprintf("task %d scheduled run=%d attempt=%d", task.ID, run.ID, attempt))
		e.Exec.Enqueue(run)
	}
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
