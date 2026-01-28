package service

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/tidwall/gjson"
	"go.opentelemetry.io/otel/trace"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_client"
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
	// Injected HTTP client with OTEL support
	HTTPCli *http_client.HTTPClientsComponent `infra:"dep:http_clients"`
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
	// Log with trace ID
	logCtx := e.ensureTraceContext(context.Background(), run.TraceID)
	logging.Info(logCtx, fmt.Sprintf("task: %d has enqueued", run.ID))
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
			// Reconstruct trace context for the worker execution scope
			runCtx := e.ensureTraceContext(context.Background(), run.TraceID)

			logging.Info(runCtx, fmt.Sprintf("task: %d grabbed in worker ok=%v", run.ID, ok))
			ok2, err := e.RunSvc.TransitionToRunning(runCtx, run.ID)
			if err != nil || !ok2 {
				if err != nil {
					logging.Info(runCtx, fmt.Sprintf("transition to running failed for run %d: %v", run.ID, err))
				}
				continue
			}
			e.execute(runCtx, run)
		}
	}
}

func (e *Executor) execute(ctx context.Context, run *model.TaskRun) {
	// 1. 加载任务
	task, err := e.TaskSvc.Get(ctx, run.TaskID)
	if err != nil {
		log.Printf("load task %d: %v", run.TaskID, err)
		_ = e.RunSvc.MarkFailed(ctx, run.ID, "load task failed")
		return
	}

	// 2. 准备 per-run 上下文 & 资源清理逻辑
	runCtx, cleanup, timeoutSec := e.startRunContext(ctx, task, run)
	defer cleanup()

	// 3. 构建 HTTP 请求
	req, err := e.buildRequest(runCtx, task, run)
	if err != nil {
		logging.Error(ctx, fmt.Sprintf("create request for task failed %d: %v", task.ID, err))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, "build request failed")
		return
	}

	// 3.1 记录本次实际发送的 request headers/body
	e.persistOutboundSnapshot(ctx, run.ID, req)

	// 4. 执行 HTTP 调用 (含分类错误)
	resp, body, classify, err := e.doHTTP(runCtx, task, run, timeoutSec, req)
	if err != nil { // 传输层或上下文异常
		// 没有 HTTP 响应，按分类更新状态
		switch classify {
		case "canceled":
			_ = e.RunSvc.MarkCanceled(ctx, run.ID)
		case "request_timeout":
			_ = e.RunSvc.MarkTimeout(ctx, run.ID, classify)
		default:
			_ = e.RunSvc.MarkFailed(ctx, run.ID, classify)
		}
		return
	}
	defer func() { _ = resp.Body.Close() }()

	// 5. 统一处理业务响应（同步/异步），并落库响应快照
	e.persistInboundSnapshot(ctx, run.ID, resp.StatusCode, string(body), "")

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		if task.ExecType == bizConsts.ExecTypeAsync { // 异步第一阶段成功
			deadline := time.Now().Add(time.Duration(task.CallbackTimeoutSec) * time.Second)
			if task.CallbackTimeoutSec <= 0 {
				deadline = time.Now().Add(5 * time.Minute)
			}
			logging.Info(ctx, fmt.Sprintf("run %d async phase1 succeeded; transitioning to CALLBACK_PENDING until deadline %s", run.ID, deadline.Format(time.RFC3339)))
			_ = e.RunSvc.MarkCallbackPendingWithDeadline(ctx, run.ID, deadline)
			return
		}
		// 同步：尝试识别业务失败
		status := gjson.GetBytes(body, "status").String()
		errMsg := gjson.GetBytes(body, "error").String()
		if strings.EqualFold(status, bizConsts.Failed.String()) || strings.TrimSpace(errMsg) != "" {
			_ = e.RunSvc.MarkFailed(ctx, run.ID, fmt.Sprintf("biz_failed: status=%s error=%s", status, errMsg))
			e.persistInboundSnapshot(ctx, run.ID, resp.StatusCode, string(body), fmt.Sprintf("biz_failed: status=%s error=%s", status, errMsg))
		} else {
			_ = e.RunSvc.MarkSuccess(ctx, run.ID, resp.StatusCode, string(body))
		}
		return
	}

	// 非 2xx：记录错误详情并标记失败
	msg := resp.Status
	if len(body) > 0 {
		msg = fmt.Sprintf("%s; body=%s", msg, string(body))
	}
	_ = e.RunSvc.MarkFailed(ctx, run.ID, msg)
	e.persistInboundSnapshot(ctx, run.ID, resp.StatusCode, string(body), msg)
}

// persistOutboundSnapshot captures the effective request headers/body and stores them into task_runs.
// It also masks obviously sensitive headers.
func (e *Executor) persistOutboundSnapshot(ctx context.Context, runID int64, req *http.Request) {
	if req == nil || e.RunSvc == nil {
		return
	}

	// collect headers into a stable JSON map (string->[]string)
	hdr := map[string][]string{}
	for k, v := range req.Header {
		if len(v) == 0 {
			continue
		}
		lk := strings.ToLower(k)
		if lk == "authorization" || lk == "cookie" || lk == "set-cookie" {
			hdr[k] = []string{"***"}
			continue
		}
		hdr[k] = v
	}
	// stable key order (json.Marshal doesn't guarantee order, but stable order helps diffing in UI).
	// We'll re-marshal via a sorted-key intermediate.
	keys := make([]string, 0, len(hdr))
	for k := range hdr {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	ordered := make(map[string]any, len(keys))
	for _, k := range keys {
		ordered[k] = hdr[k]
	}
	headersJSON := bizConsts.DEFAULT_JSON_STR
	if b, err := json.Marshal(ordered); err == nil {
		headersJSON = string(b)
	}

	// request body: best-effort. buildRequest always uses bytes.NewReader, so GetBody may be nil.
	bodyStr := ""
	if req.GetBody != nil {
		if rc, err := req.GetBody(); err == nil {
			bb, _ := io.ReadAll(rc)
			_ = rc.Close()
			bodyStr = string(bb)
		}
	}

	_ = e.RunSvc.UpdateRequestSnapshot(ctx, runID, headersJSON, bodyStr)
}

// persistInboundSnapshot stores downstream response snapshot.
func (e *Executor) persistInboundSnapshot(ctx context.Context, runID int64, code int, body string, errMsg string) {
	c := code
	_ = e.RunSvc.UpdateResponseSnapshot(ctx, runID, &c, body, errMsg)
}

// startRunContext 计算任务超时时间，创建带超时的上下文，并登记取消函数 + 运行中计数。
// 返回：子上下文、清理函数（负责取消与计数回收）、timeout(秒)
func (e *Executor) startRunContext(parent context.Context, task *model.Task, run *model.TaskRun) (context.Context, func(), int) {
	// The parent context passed here (from worker) should already have trace info via ensureTraceContext.
	// We can add another span layer specifically for the execution phase if desired, or just use parent.
	// For simplicity and to ensure trace existence even if called from elsewhere:
	baseCtx := e.ensureTraceContext(parent, run.TraceID)

	to := task.TimeoutSeconds
	if to <= 0 {
		to = 10
	}
	runCtx, cancel := context.WithTimeout(baseCtx, time.Duration(to)*time.Second)

	e.mu.Lock()
	e.cancelMap[run.ID] = cancel
	e.activePerTask[task.ID]++
	e.mu.Unlock()

	cleanup := func() {
		cancel()
		e.mu.Lock()
		delete(e.cancelMap, run.ID)
		e.activePerTask[task.ID]--
		if e.activePerTask[task.ID] <= 0 {
			delete(e.activePerTask, task.ID)
		}
		e.mu.Unlock()
	}
	return runCtx, cleanup, to
}

// ensureTraceContext creates a new context with a span context derived from the traceID string.
// If traceID is empty or invalid, it returns the parent context.
// It generates a new random SpanID to represent a local operation within that trace.
func (e *Executor) ensureTraceContext(parent context.Context, traceID string) context.Context {
	if traceID == "" {
		return parent
	}
	// If parent already has this trace ID, we might just return parent or create a child span.
	// Here we force creating a new SpanContext to ensure "remote" flag behavior or just fresh span.
	tid, err := trace.TraceIDFromHex(traceID)
	if err != nil {
		return parent
	}

	// Create a new SpanID
	var sid trace.SpanID
	_, _ = rand.Read(sid[:])

	sc := trace.NewSpanContext(trace.SpanContextConfig{
		TraceID:    tid,
		SpanID:     sid,
		TraceFlags: trace.FlagsSampled,
		Remote:     true,
	})
	return trace.ContextWithSpanContext(parent, sc)
}

// buildRequest 根据任务配置构建 HTTP 请求。调整：不再在 URL 上附带 run_id 参数；使用 JSON 包含 meta(A) 与 body(B)。
func (e *Executor) buildRequest(ctx context.Context, task *model.Task, run *model.TaskRun) (*http.Request, error) {
	// A: meta 信息 (run 相关)
	ce := config.GetBizConfig().CallbackEndpoints
	progressPath := ce.ProgressPath
	callbackPath := ce.CallbackPath
	if progressPath == "" {
		progressPath = "/runs/{run_id}/progress"
	}
	if callbackPath == "" {
		callbackPath = "/runs/{run_id}/callback"
	}
	progressPath = strings.ReplaceAll(progressPath, "{run_id}", fmt.Sprintf("%d", run.ID))
	callbackPath = strings.ReplaceAll(callbackPath, "{run_id}", fmt.Sprintf("%d", run.ID))
	meta := map[string]any{
		"run_id":    run.ID,
		"task_id":   task.ID,
		"exec_type": task.ExecType,
		"callback_endpoints": map[string]any{
			"progress": progressPath,
			"callback": callbackPath,
			//"callback_ip":   bizConsts.LocalIP,
			//"callback_port": application.GetApp().GetConfig().HTTPServer.Address,
		},
	}
	// B: 业务 body, 来自 task.BodyTemplate (保留原始字符串或 JSON)
	var bodyVal any = nil
	if task.BodyTemplate != "" {
		var js any
		if err := json.Unmarshal([]byte(task.BodyTemplate), &js); err == nil { // 有效 JSON
			bodyVal = js
		} else {
			bodyVal = task.BodyTemplate
		}
	}
	payload := map[string]any{"meta": meta, "body": bodyVal}
	buf, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal outbound payload failed: %w", err)
	}
	// URL 不再附带 run_id
	urlFinal := task.TargetURL
	req, err := http.NewRequestWithContext(ctx, task.HTTPMethod, urlFinal, bytes.NewReader(buf))
	if err != nil {
		return nil, err
	}
	// Allow re-reading body for persistence without consuming the request stream.
	req.GetBody = func() (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(buf)), nil
	}

	// Headers: caller identity
	req.Header.Set("Content-Type", "application/json")
	//req.Header.Set("X-Caller-IP", bizConsts.LocalIP)
	//req.Header.Set("X-Caller-Port", application.GetApp().GetConfig().HTTPServer.Address)
	return req, nil
}

// doHTTP 执行 HTTP 请求并读取响应 Body。
// 返回：resp(成功时)/nil, body(成功时), 分类字符串(错误时), error
func (e *Executor) doHTTP(ctx context.Context, task *model.Task, run *model.TaskRun, timeoutSec int, req *http.Request) (*http.Response, []byte, string, error) {
	var resp *http.Response
	var err error

	if e.HTTPCli != nil {
		cli, _ := e.HTTPCli.Client("artemis")
		resp, err = cli.Client.Do(req)
	} else {
		// Fallback if component not injected
		client := &http.Client{Timeout: time.Duration(timeoutSec) * time.Second}
		resp, err = client.Do(req)
	}

	if err != nil { // 需要分类
		classify := e.classifyNetError(ctx, err)
		logging.Error(ctx, fmt.Sprintf("task %d request failed %d classified=%s raw=%v", task.ID, run.ID, classify, err))
		return nil, nil, classify, err
	}
	b, _ := io.ReadAll(resp.Body)
	// 注意：调用者仍负责 resp.Body 的关闭，本处只是预读。
	// 将 body 放入日志 (调试级别)
	logging.Debug(ctx, fmt.Sprintf("task: %d resp.StatusCode :%d, response body: %s", task.ID, resp.StatusCode, b))
	return resp, b, "", nil
}

// classifyNetError 按既有逻辑对网络/上下文错误进行归类。
func (e *Executor) classifyNetError(ctx context.Context, err error) string {
	// 优先检查上下文状态
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return "request_timeout"
	}
	if errors.Is(ctx.Err(), context.Canceled) {
		return "canceled"
	}
	// 尝试按底层网络错误分类
	msg := err.Error()
	var opErr *net.OpError
	if errors.As(err, &opErr) {
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
	return msg
}

func (e *Executor) CancelRun(id int64) {
	e.mu.Lock()
	cancel, ok := e.cancelMap[id]
	e.mu.Unlock()
	if ok {
		cancel()
	}
}
