package scheduler

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
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// Engine component; dependencies injected via tags.
type Engine struct {
	cfg     config.SchedulerConfig
	TaskDao dao.TaskDao        `infra:"dep:task_dao"`
	RunDao  dao.RunDao         `infra:"dep:run_dao"`
	Exec    *executor.Executor `infra:"dep:executor"`
	*core.BaseComponent
	cancel context.CancelFunc
	wg     sync.WaitGroup
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
	tasks, err := e.TaskDao.ListEnabled(ctx)
	if err != nil {
		return err
	}
	sec := now.Truncate(time.Second)
	for _, t := range tasks {
		if !shouldFire(sec, t.CronExpr) {
			continue
		}
		logging.Info(ctx, fmt.Sprintf("task: %d should run", t.ID))
		if t.MaxConcurrency > 0 && t.ConcurrencyPolicy == model.ConcurrencySkip && e.Exec.ActiveCount(t.ID) >= t.MaxConcurrency {
			run := &model.TaskRun{TaskID: t.ID, ScheduledTime: sec, Status: model.RunStatusScheduled, Attempt: 1}
			if err := e.RunDao.CreateScheduled(ctx, run); err == nil {
				_ = e.RunDao.MarkSkipped(ctx, run.ID)
			}
			continue
		}
		run := &model.TaskRun{TaskID: t.ID, ScheduledTime: sec, Status: model.RunStatusScheduled, Attempt: 1}
		if err := e.RunDao.CreateScheduled(ctx, run); err != nil {
			continue
		}
		logging.Info(ctx, fmt.Sprintf("task: %d prepared enqueued", t.ID))
		e.Exec.Enqueue(run)
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
