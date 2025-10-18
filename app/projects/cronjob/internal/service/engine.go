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

// Engine component; dependencies injected via tags.
type Engine struct {
	cfg     config.SchedulerConfig
	TaskSvc *TaskService `infra:"dep:task_service"`
	RunDao  dao.RunDao   `infra:"dep:run_dao"`
	Exec    *Executor    `infra:"dep:executor"`
	*core.BaseComponent
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	lastScanSec time.Time // 上次扫描的秒级时间戳（截断到秒）
}

func NewEngine(cfg config.SchedulerConfig) *Engine {
	if cfg.PollInterval <= 0 {
		cfg.PollInterval = time.Second
	}
	return &Engine{
		cfg:           cfg,
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SCHEDULER),
	}
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
	e.lastScanSec = time.Now().Truncate(time.Second)
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

func (e *Engine) scan(ctx context.Context, now time.Time) error {
	tasks, err := e.TaskSvc.ListEnabled(ctx)
	if err != nil {
		return err
	}
	sec := now.Truncate(time.Second)
	// 构造从 lastScanSec+1 到当前 sec 的秒列表（包含当前秒）
	var candidateSeconds []time.Time
	// This loop generates a list of all second-level timestamps from the next second after e.lastScanSec up to and including the current second (sec),
	// and appends them to candidateSeconds.
	for tcur := e.lastScanSec.Add(time.Second); !tcur.After(sec); tcur = tcur.Add(time.Second) {
		candidateSeconds = append(candidateSeconds, tcur)
	}
	e.lastScanSec = sec

	for _, t := range tasks {
		// 过滤匹配 Cron 的秒
		var matched []time.Time
		for _, ts := range candidateSeconds {
			if shouldFire(ts, t.CronExpr) {
				matched = append(matched, ts)
			}
		}
		if len(matched) == 0 {
			continue
		}
		// 应用 MisfirePolicy
		var toSchedule []time.Time
		switch t.MisfirePolicy {
		case bizConsts.MisfireFireNow:
			toSchedule = matched
		case bizConsts.MisfireSkip:
			// 仅调度当前最新秒（如果包含当前）
			for _, m := range matched {
				if m.Equal(sec) { // only current second
					toSchedule = append(toSchedule, m)
				}
			}
		case bizConsts.MisfireCatchUpLimited:
			limit := t.CatchupLimit
			if limit <= 0 || limit > len(matched) {
				limit = len(matched)
			}
			toSchedule = matched[len(matched)-limit:]
		default:
			toSchedule = matched
		}

		// 获取最近一次 run（用于策略判断）
		var lastRun *model.TaskRun
		runs, _ := e.RunDao.ListByTask(ctx, t.ID, 1)
		if len(runs) > 0 {
			lastRun = runs[0]
		}

		for _, fireTime := range toSchedule {
			logging.Info(ctx, fmt.Sprintf("task %d evaluating fire at %s", t.ID, fireTime.Format(time.RFC3339)))

			// Overlap 检测：上一轮仍 RUNNING 并且 start_time 在该触发时间之前
			overlap := lastRun != nil && lastRun.Status == bizConsts.Running

			// Failure 检测：上一轮已失败/超时/取消
			failedPrev := false
			if lastRun != nil {
				switch lastRun.Status {
				case bizConsts.Failed, bizConsts.Timeout, bizConsts.FailedTimeout, bizConsts.Canceled:
					failedPrev = true
				}
			}

			// 处理 OverlapAction
			ignoreConcurrency := false
			if overlap {
				switch t.OverlapAction {
				case bizConsts.OverlapSkip:
					// 记录一次 scheduled+skipped
					run := &model.TaskRun{TaskID: t.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: 1}
					if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
						_ = e.RunDao.MarkSkipped(ctx, run.ID)
					}
					continue
				case bizConsts.OverlapCancelPrev:
					if lastRun != nil {
						// 主动取消上一轮
						e.Exec.CancelRun(lastRun.ID)
						_ = e.RunDao.MarkCanceled(ctx, lastRun.ID)
					}
				case bizConsts.OverlapParallel:
					ignoreConcurrency = true
				case bizConsts.OverlapAllow:
					// 按原逻辑继续
				}
			}

			attempt := 1
			if failedPrev {
				switch t.FailureAction {
				case bizConsts.FailureSkip:
					run := &model.TaskRun{TaskID: t.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: lastRun.Attempt + 1}
					if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
						_ = e.RunDao.MarkSkipped(ctx, run.ID)
					}
					continue
				case bizConsts.FailureRetry:
					attempt = lastRun.Attempt + 1
				case bizConsts.FailureRunNew:
					attempt = 1
				}
			}

			// 并发策略 (如果没有 ignoreConcurrency)
			if !ignoreConcurrency && t.MaxConcurrency > 0 && e.Exec.ActiveCount(t.ID) >= t.MaxConcurrency {
				if t.ConcurrencyPolicy == bizConsts.ConcurrencySkip {
					run := &model.TaskRun{TaskID: t.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: attempt}
					if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
						_ = e.RunDao.MarkSkipped(ctx, run.ID)
					}
					continue
				}
				// QUEUE 策略：仍然入队（当前实现与 parallel 类似），PARALLEL 已允许直接入队。
			}

			run := &model.TaskRun{TaskID: t.ID, ScheduledTime: fireTime, Status: bizConsts.Scheduled, Attempt: attempt}
			if err := e.RunDao.CreateScheduled(ctx, run); err != nil {
				logging.Info(ctx, fmt.Sprintf("create scheduled run failed task=%d time=%s err=%v", t.ID, fireTime, err))
				continue
			}
			logging.Info(ctx, fmt.Sprintf("task %d scheduled run %d at %s attempt=%d", t.ID, run.ID, fireTime.Format(time.RFC3339), attempt))
			e.Exec.Enqueue(run)
			lastRun = run // 更新 lastRun 以便后续 fireTime 策略判断
		}
	}
	return nil
}

// Very simplified cron matcher supporting:
// - "*" wildcard
// - exact numbers (e.g. 5)
// - comma lists (e.g. 0,15,30,45)
// - step syntax "*/N" (value % N == 0)
// Note: ranges like 1-10 or 1-10/2 not yet supported.
func shouldFire(t time.Time, expr string) bool {
	fields := splitFields(expr)
	if len(fields) != 6 {
		return false
	}
	vals := []int{t.Second(), t.Minute(), t.Hour(), t.Day(), int(t.Month()), int(t.Weekday())}
	for i, f := range fields {
		if f == "*" {
			continue
		}
		matched := false
		for _, part := range splitComma(f) {
			part = strings.TrimSpace(part)
			if part == "*" {
				matched = true
				break
			}
			if len(part) > 2 && part[:2] == "*/" { // step pattern
				step := toInt(part[2:])
				if step > 0 && vals[i]%step == 0 {
					matched = true
					break
				}
				continue
			}
			if toInt(part) == vals[i] {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

func splitFields(s string) []string {
	var r []string
	cur := ""
	for _, c := range s {
		if c == ' ' {
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
	for _, c := range s {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		} else {
			return -1
		}
	}
	return n
}
