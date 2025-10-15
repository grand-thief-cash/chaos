package scheduler

import (
	"context"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type Config struct {
	PollInterval time.Duration
}

type Engine struct {
	cfg     Config
	taskDao dao.TaskDao
	runDao  dao.RunDao
	exec    *executor.Executor
	started bool
	mu      sync.Mutex
}

func NewEngine(tr dao.TaskDao, rr dao.RunDao, exec *executor.Executor, cfg Config) *Engine {
	return &Engine{cfg: cfg, taskDao: tr, runDao: rr, exec: exec}
}

func (e *Engine) Start(ctx context.Context) {
	e.mu.Lock()
	if e.started {
		e.mu.Unlock()
		return
	}
	e.started = true
	e.mu.Unlock()
	ticker := time.NewTicker(e.cfg.PollInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			log.Println("scheduler stopped")
			return
		case now := <-ticker.C:
			if err := e.scan(ctx, now); err != nil {
				log.Printf("scheduler scan err: %v", err)
			}
		}
	}
}

func (e *Engine) scan(ctx context.Context, now time.Time) error {
	tasks, err := e.taskDao.ListEnabled(ctx)
	if err != nil {
		return err
	}
	sec := now.Truncate(time.Second)
	for _, t := range tasks {
		if !shouldFire(sec, t.CronExpr) {
			continue
		}
		// concurrency skip policy
		if t.MaxConcurrency > 0 && t.ConcurrencyPolicy == model.ConcurrencySkip && e.exec.ActiveCount(t.ID) >= t.MaxConcurrency {
			// record skipped run for observability
			run := &model.TaskRun{TaskID: t.ID, ScheduledTime: sec, Status: model.RunStatusScheduled, Attempt: 1}
			if err := e.runDao.CreateScheduled(ctx, run); err == nil {
				//MarkSkipped 的作用是将某个任务运行（run）的状态标记为“已跳过”。
				//当任务因并发策略被跳过时，先创建一个调度记录（CreateScheduled），
				//然后通过 MarkSkipped 更新该记录的状态，方便后续统计、监控和排查任务为何未执行。这样可以提升系统的可观测性和可维护性
				_ = e.runDao.MarkSkipped(ctx, run.ID)
			}
			continue
		}
		// create run
		run := &model.TaskRun{TaskID: t.ID, ScheduledTime: sec, Status: model.RunStatusScheduled, Attempt: 1}
		if err := e.runDao.CreateScheduled(ctx, run); err != nil {
			continue
		}
		// enqueue; queue policy currently immediate (Phase2: true queue)
		// parallel just enqueues as well
		e.exec.Enqueue(run)
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
