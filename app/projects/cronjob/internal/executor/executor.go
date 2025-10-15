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

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type Config struct {
	WorkerPoolSize int
	RequestTimeout time.Duration
}

type Executor struct {
	cfg           Config
	tr            dao.TaskDao
	rr            dao.RunDao
	ch            chan *model.TaskRun
	wg            sync.WaitGroup
	mu            sync.Mutex
	cancelMap     map[int64]context.CancelFunc
	activePerTask map[int64]int // taskID -> running count
}

func NewExecutor(cfg Config, tr dao.TaskDao, rr dao.RunDao) *Executor {
	return &Executor{cfg: cfg, tr: tr, rr: rr, ch: make(chan *model.TaskRun, 1024), cancelMap: make(map[int64]context.CancelFunc), activePerTask: make(map[int64]int)}
}

func (e *Executor) Start(ctx context.Context) {
	for i := 0; i < e.cfg.WorkerPoolSize; i++ {
		e.wg.Add(1)
		go e.worker(ctx)
	}
}

func (e *Executor) Enqueue(run *model.TaskRun) { e.ch <- run }

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
			return
		case run := <-e.ch:
			if run == nil {
				continue
			}
			ok, err := e.rr.TransitionToRunning(ctx, run.ID)
			if err != nil || !ok {
				continue
			}
			e.execute(ctx, run)
		}
	}
}

func (e *Executor) execute(ctx context.Context, run *model.TaskRun) {
	// load task
	task, err := e.tr.Get(ctx, run.TaskID)
	if err != nil {
		log.Printf("load task %d: %v", run.TaskID, err)
		_ = e.rr.MarkFailed(ctx, run.ID, "load task failed")
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
		_ = e.rr.MarkFailed(ctx, run.ID, "build request failed")
		return
	}
	client := &http.Client{Timeout: time.Duration(task.TimeoutSeconds) * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("HTTP request error: %v\n", err)
		select {
		case <-ctx2.Done():
			_ = e.rr.MarkFailed(ctx, run.ID, "canceled or timeout")
		default:
			_ = e.rr.MarkFailed(ctx, run.ID, err.Error())
		}
		return
	}
	fmt.Printf("Response: %+v\n", resp)
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		fmt.Println(resp.StatusCode, string(b))
		_ = e.rr.MarkSuccess(ctx, run.ID, resp.StatusCode, string(b))
	} else {
		_ = e.rr.MarkFailed(ctx, run.ID, resp.Status)
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
