package service

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"sync"
	"syscall"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
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
	TaskSvc *TaskService `infra:"dep:task_service"`
	RunSvc  *RunService  `infra:"dep:run_service"`
	ch      chan *model.TaskRun
	wg      sync.WaitGroup
	mu      sync.Mutex
	cancel  context.CancelFunc
	// In execute we create timeout contexts per run; cancelMap stores per-run cancel funcs.
	cancelMap     map[int64]context.CancelFunc // runID -> cancel func
	activePerTask map[int64]int                // taskID -> running count
	Progress      *RunProgressManager          `infra:"dep:run_progress_mgr"`
}

func NewExecutor(cfg config.ExecutorConfig) *Executor {
	if cfg.WorkerPoolSize <= 0 {
		cfg.WorkerPoolSize = 4
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = 15 * time.Second
	}
	return &Executor{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_EXECUTOR, consts.COMPONENT_LOGGING),
		cfg:           cfg,
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
	// Snapshot active run IDs to cancel before stopping
	var activeIDs []int64
	e.mu.Lock()
	for rid := range e.cancelMap {
		activeIDs = append(activeIDs, rid)
	}
	e.mu.Unlock()
	for _, rid := range activeIDs {
		e.CancelRun(rid)
	}
	if e.cancel != nil {
		e.cancel()
	}
	// drain channel by closing (workers exit on ctx cancel anyway). Avoid panic on double close.
	e.mu.Lock()
	if e.ch != nil {
		close(e.ch)
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
			ok2, err := e.RunSvc.TransitionToRunning(ctx, run.ID)
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
	task, err := e.TaskSvc.Get(ctx, run.TaskID)
	if err != nil {
		log.Printf("load task %d: %v", run.TaskID, err)
		_ = e.RunSvc.MarkFailed(ctx, run.ID, "load task failed")
		return
	}

	// derive per-run context with timeout
	to := task.TimeoutSeconds
	if to <= 0 {
		to = 10
	}
	ctx2, cancel := context.WithTimeout(ctx, time.Duration(to)*time.Second)
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
	urlWithRunID := fmt.Sprintf("%s?run_id=%d", task.TargetURL, run.ID)
	req, err := http.NewRequestWithContext(ctx2, task.HTTPMethod, urlWithRunID, body)
	if err != nil {
		logging.Error(ctx, fmt.Sprintf("create request for task failed %d: %v", task.ID, err))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, "build request failed")
		return
	}

	client := &http.Client{Timeout: time.Duration(to) * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		// differentiate error source
		if ctx2.Err() == context.DeadlineExceeded {
			logging.Error(ctx, fmt.Sprintf("task %d timeout exceeded", task.ID))
			_ = e.RunSvc.MarkTimeout(ctx, run.ID, "request_timeout")
			return
		}
		if ctx2.Err() == context.Canceled {
			// explicit cancel
			_ = e.RunSvc.MarkCanceled(ctx, run.ID)
			return
		}
		// network error classification
		msg := err.Error()
		var opErr *net.OpError
		if errors.As(err, &opErr) {
			// check inner error types
			switch {
			case errors.Is(opErr.Err, syscall.ECONNREFUSED):
				msg = "connection_refused"
			case errors.Is(opErr.Err, syscall.ETIMEDOUT):
				msg = "connect_timeout"
			case errors.Is(opErr.Err, syscall.ENETUNREACH):
				msg = "network_unreachable"
			case errors.Is(opErr.Err, syscall.EHOSTUNREACH):
				msg = "host_unreachable"
			}
		} else if nErr, ok := err.(net.Error); ok && nErr.Timeout() {
			msg = "request_timeout"
		}
		logging.Error(ctx, fmt.Sprintf("task %d request failed %d classified=%s raw=%v", task.ID, run.ID, msg, err))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, msg)
		return
	}
	defer func() { _ = resp.Body.Close() }()
	b, _ := io.ReadAll(resp.Body)
	logging.Debug(ctx, fmt.Sprintf("task: %d resp.StatusCode :%d, response body: %s", task.ID, resp.StatusCode, b))
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		if task.ExecType == bizConsts.ExecTypeAsync { // async first phase success -> callback pending (never mark Success here)
			deadline := time.Now().Add(time.Duration(task.CallbackTimeoutSec) * time.Second)
			if task.CallbackTimeoutSec <= 0 {
				deadline = time.Now().Add(5 * time.Minute)
			}
			logging.Info(ctx, fmt.Sprintf("run %d async phase1 succeeded; transitioning to CALLBACK_PENDING until deadline %s", run.ID, deadline.Format(time.RFC3339)))
			_ = e.RunSvc.MarkCallbackPendingWithDeadline(ctx, run.ID, deadline)
			// progress retained for callback phase; external callback should clear if desired
		} else { // sync final success
			_ = e.RunSvc.MarkSuccess(ctx, run.ID, resp.StatusCode, string(b))
			if e.Progress != nil {
				e.Progress.Clear(run.ID)
			}
		}
	} else {
		_ = e.RunSvc.MarkFailed(ctx, run.ID, resp.Status)
		if e.Progress != nil {
			e.Progress.Clear(run.ID)
		}
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
