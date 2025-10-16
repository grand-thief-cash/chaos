package executor

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// Config holds executor runtime parameters
//type Config struct {
//	WorkerPoolSize int
//	RequestTimeout time.Duration
//}

type Executor struct {
	*core.BaseComponent

	cfg     config.ExecutorConfig
	taskDao dao.TaskDao
	runDao  dao.RunDao
	ch      chan *model.TaskRun
	wg      sync.WaitGroup
	mu      sync.Mutex
	cancel  context.CancelFunc
	// In execute we create timeout contexts per run; cancelMap stores per-run cancel funcs.
	cancelMap     map[int64]context.CancelFunc // runID -> cancel func
	activePerTask map[int64]int                // taskID -> running count
}

func NewExecutor(cfg config.ExecutorConfig, taskDao dao.TaskDao, runDao dao.RunDao) *Executor {
	if cfg.WorkerPoolSize <= 0 {
		cfg.WorkerPoolSize = 4
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = 15 * time.Second
	}
	return &Executor{
		BaseComponent: core.NewBaseComponent("executor", "task_dao", "run_dao", consts.COMPONENT_LOGGING),
		cfg:           cfg,
		taskDao:       taskDao,
		runDao:        runDao,
		ch:            make(chan *model.TaskRun, 1024),
		cancelMap:     make(map[int64]context.CancelFunc),
		activePerTask: make(map[int64]int),
	}
}

// Start implements core.Component
func (e *Executor) Start(ctx context.Context) error {
	if e.IsActive() { // idempotent
		return nil
	}
	if err := e.BaseComponent.Start(ctx); err != nil { // set active flag
		return err
	}
	// IMPORTANT: lifecycle manager cancels the ctx passed to Start right after Start returns.
	// Derive a new background context for long-lived workers so they don't exit immediately.
	loopCtx, cancel := context.WithCancel(context.Background())
	e.cancel = cancel
	// start workers
	for i := 0; i < e.cfg.WorkerPoolSize; i++ {
		e.wg.Add(1)
		logging.Info(loopCtx, fmt.Sprintf("Starting worker: %d", i))
		go e.worker(loopCtx)
	}
	return nil
}

// Stop implements core.Component
func (e *Executor) Stop(ctx context.Context) error {
	if !e.IsActive() { // already stopped
		return nil
	}
	if e.cancel != nil {
		e.cancel()
	}
	// drain channel by closing (workers exit on ctx cancel anyway). Avoid panic on double close.
	e.mu.Lock()
	ch := e.ch
	if ch != nil {
		close(e.ch)
		// mark nil to avoid re-close
		e.ch = nil
	}
	e.mu.Unlock()
	e.wg.Wait()
	return e.BaseComponent.Stop(ctx)
}

func (e *Executor) Enqueue(run *model.TaskRun) { // exposed API
	e.mu.Lock()
	if e.ch == nil { // stopped
		e.mu.Unlock()
		return
	}
	e.mu.Unlock()
	e.ch <- run
	logging.Info(context.Background(), fmt.Sprintf("task: %d has enqueued", run.ID))
}

func (e *Executor) ActiveCount(taskID int64) int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.activePerTask[taskID]
}

func (e *Executor) worker(ctx context.Context) {
	defer e.wg.Done()
	for {
		select {
		case <-ctx.Done():
			logging.Info(context.Background(), "worker context canceled; exiting")
			return
		case run, ok := <-e.ch:
			if !ok { // channel closed
				logging.Info(context.Background(), "channel closed; worker exiting")
				return
			}
			if run == nil {
				continue
			}
			logging.Info(ctx, fmt.Sprintf("task: %d grabbed in worker ok=%v", run.ID, ok))
			ok2, err := e.runDao.TransitionToRunning(ctx, run.ID)
			if err != nil || !ok2 {
				if err != nil {
					logging.Info(ctx, fmt.Sprintf("transition to running failed for run %d: %v", run.ID, err))
				}
				continue
			}
			e.execute(ctx, run)
		}
	}
}

func (e *Executor) execute(ctx context.Context, run *model.TaskRun) {
	// load task
	task, err := e.taskDao.Get(ctx, run.TaskID)
	if err != nil {
		log.Printf("load task %d: %v", run.TaskID, err)
		_ = e.runDao.MarkFailed(ctx, run.ID, "load task failed")
		return
	}

	ctx2, cancel := context.WithTimeout(ctx, time.Duration(task.TimeoutSeconds)*time.Second)
	e.mu.Lock()
	e.cancelMap[run.ID] = cancel
	e.activePerTask[task.ID]++
	e.mu.Unlock()
	defer func() {
		cancel()
		e.mu.Lock()
		delete(e.cancelMap, run.ID)
		e.activePerTask[task.ID]--
		if e.activePerTask[task.ID] <= 0 {
			delete(e.activePerTask, task.ID)
		}
		e.mu.Unlock()
	}()

	var body io.Reader
	if task.BodyTemplate != "" {
		body = bytes.NewBufferString(task.BodyTemplate)
	}
	tB, _ := json.Marshal(task)
	fmt.Println(fmt.Sprintf("task: %s", string(tB)))
	req, err := http.NewRequestWithContext(ctx2, task.HTTPMethod, task.TargetURL, body)
	fmt.Println(fmt.Sprintf("targetURL: %s, HTTPMethod: %s", task.TargetURL, task.HTTPMethod))
	if err != nil {
		_ = e.runDao.MarkFailed(ctx, run.ID, "build request failed")
		return
	}
	client := &http.Client{Timeout: time.Duration(task.TimeoutSeconds) * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("HTTP request error: %v\n", err)
		select {
		case <-ctx2.Done():
			_ = e.runDao.MarkFailed(ctx, run.ID, "canceled or timeout")
		default:
			_ = e.runDao.MarkFailed(ctx, run.ID, err.Error())
		}
		return
	}
	fmt.Printf("Response: %+v\n", resp)
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		fmt.Println(resp.StatusCode, string(b))
		_ = e.runDao.MarkSuccess(ctx, run.ID, resp.StatusCode, string(b))
	} else {
		_ = e.runDao.MarkFailed(ctx, run.ID, resp.Status)
	}
}

func (e *Executor) CancelRun(id int64) {
	e.mu.Lock()
	cancel, ok := e.cancelMap[id]
	e.mu.Unlock()
	if ok {
		cancel()
	}
}
