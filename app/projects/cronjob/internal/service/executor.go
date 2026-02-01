package service

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
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
	HTTPCli       *http_client.HTTPClientsComponent `infra:"dep:http_clients"`
	ch            chan *model.TaskRun
	wg            sync.WaitGroup
	mu            sync.Mutex
	cancel        context.CancelFunc
	cancelMap     map[int64]context.CancelFunc // runID -> cancel func 	// In execute we create timeout contexts per run; cancelMap stores per-run cancel funcs.
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
			traceCtx := e.ensureTraceContext(context.Background(), run.TraceID)

			logging.Info(traceCtx, fmt.Sprintf("task: %d grabbed in worker ok=%v", run.ID, ok))
			ok2, err := e.RunSvc.TransitionToRunning(traceCtx, run.ID)
			if err != nil || !ok2 {
				if err != nil {
					logging.Info(traceCtx, fmt.Sprintf("transition to running failed for run %d: %v", run.ID, err))
				}
				continue
			}
			e.execute(traceCtx, run)
		}
	}
}

func (e *Executor) execute(ctx context.Context, run *model.TaskRun) {
	// 2. 准备 per-run 上下文 & 资源清理逻辑
	runCtx, cleanup := e.startRunContext(ctx, run)
	defer cleanup()

	// 2.5 获取客户端并解析完整 URL
	targetService := run.TargetService
	if targetService == "" {
		errMsg := "target_service is empty"
		logging.Error(ctx, fmt.Sprintf("run %d failed: %s", run.ID, errMsg))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, errMsg)
		return
	}

	var client *http_client.InstrumentedClient
	var errCli error
	if e.HTTPCli != nil {
		client, errCli = e.HTTPCli.Client(targetService)
	} else {
		// Fallback (mostly for tests or incomplete initialization)
		client = &http_client.InstrumentedClient{Client: &http.Client{Timeout: 15 * time.Second}}
	}

	if errCli != nil {
		logging.Error(ctx, fmt.Sprintf("http client for service %s not found: %v", targetService, errCli))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, fmt.Sprintf("client_config_error: %v", errCli))
		return
	}

	// Resolve full URL
	fullURL := run.TargetPath
	if !strings.HasPrefix(fullURL, "http://") && !strings.HasPrefix(fullURL, "https://") {
		baseURL := client.BaseURL
		// simple joining, assuming valid segments. Ideally use url.JoinPath but we do string concat for now
		if !strings.HasSuffix(baseURL, "/") && !strings.HasPrefix(fullURL, "/") {
			fullURL = baseURL + "/" + fullURL
		} else if strings.HasSuffix(baseURL, "/") && strings.HasPrefix(fullURL, "/") {
			fullURL = baseURL + strings.TrimPrefix(fullURL, "/")
		} else {
			fullURL = baseURL + fullURL
		}
	}

	// 3. 构建 HTTP 请求
	req, err := e.buildRequest(runCtx, run, fullURL)
	if err != nil {
		logging.Error(ctx, fmt.Sprintf("create request for task failed %d (run %d): %v", run.TaskID, run.ID, err))
		_ = e.RunSvc.MarkFailed(ctx, run.ID, "build request failed")
		return
	}

	// 3.1 记录本次实际发送的 request headers/body
	e.persistOutboundSnapshot(ctx, run.ID, req)

	// 4. 执行 HTTP 调用 (含分类错误)
	resp, body, classify, err := e.doHTTP(runCtx, client.Client, req)
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
		if run.ExecType == bizConsts.ExecTypeAsync { // 异步第一阶段成功
			// Calculate deadline from current time (when downstream accepted the task)
			timeoutSec := run.CallbackTimeoutSec
			if timeoutSec <= 0 {
				timeoutSec = 300 // Default 5 minutes if not configured
			}
			deadline := time.Now().Add(time.Duration(timeoutSec) * time.Second)
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

// startRunContext 创建带超时的上下文（默认1小时兜底），并登记取消函数 + 运行中计数。
func (e *Executor) startRunContext(parent context.Context, run *model.TaskRun) (context.Context, func()) {
	// The parent context passed here (from worker) should already have trace info via ensureTraceContext.
	baseCtx := e.ensureTraceContext(parent, run.TraceID)

	// Hard limit of 1 hour to prevent stuck goroutines if HTTP client timeout fails
	to := 3600
	runCtx, cancel := context.WithTimeout(baseCtx, time.Duration(to)*time.Second)

	e.mu.Lock()
	e.cancelMap[run.ID] = cancel
	e.activePerTask[run.TaskID]++
	e.mu.Unlock()

	cleanup := func() {
		cancel()
		e.mu.Lock()
		delete(e.cancelMap, run.ID)
		e.activePerTask[run.TaskID]--
		if e.activePerTask[run.TaskID] <= 0 {
			delete(e.activePerTask, run.TaskID)
		}
		e.mu.Unlock()
	}
	return runCtx, cleanup
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

// buildRequest 根据 TaskRun 快照构建 HTTP 请求
func (e *Executor) buildRequest(ctx context.Context, run *model.TaskRun, fullURL string) (*http.Request, error) {
	// A: meta 信息 (run 相关) - 依然构造，保持 contract 兼容
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
		"task_id":   run.TaskID,
		"exec_type": run.ExecType,
		"callback_endpoints": map[string]any{
			"progress": progressPath,
			"callback": callbackPath,
		},
	}
	// B: 业务 body, 来自 run.RequestBody (snapshot)
	var bodyVal any = nil
	if run.RequestBody != "" {
		var js any
		if err := json.Unmarshal([]byte(run.RequestBody), &js); err == nil { // 有效 JSON
			bodyVal = js
		} else {
			bodyVal = run.RequestBody
		}
	}
	payload := map[string]any{"meta": meta, "body": bodyVal}
	buf, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal outbound payload failed: %w", err)
	}

	// URL 使用 fullURL
	req, err := http.NewRequestWithContext(ctx, run.Method, fullURL, bytes.NewReader(buf))
	if err != nil {
		return nil, err
	}
	// Allow re-reading body for persistence without consuming the request stream.
	req.GetBody = func() (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(buf)), nil
	}

	// Headers: 基础 Content-Type, 后续可从 run.RequestHeaders 叠加
	req.Header.Set("Content-Type", "application/json")
	if run.RequestHeaders != "" {
		// Try parsing as simple map first
		var simpleHeaders map[string]string
		if err := json.Unmarshal([]byte(run.RequestHeaders), &simpleHeaders); err == nil {
			for k, v := range simpleHeaders {
				req.Header.Set(k, v)
			}
		} else {
			// Try multi-value map
			var multiHeaders map[string][]string
			if err := json.Unmarshal([]byte(run.RequestHeaders), &multiHeaders); err == nil {
				for k, vv := range multiHeaders {
					for _, v := range vv {
						req.Header.Add(k, v)
					}
				}
			}
		}
	}
	return req, nil
}

// doHTTP 执行 HTTP 请求并读取响应 Body。
// 仅依赖 client 和 req
func (e *Executor) doHTTP(ctx context.Context, client *http.Client, req *http.Request) (*http.Response, []byte, string, error) {
	var resp *http.Response
	var err error

	resp, err = client.Do(req)

	if err != nil { // 需要分类
		classify := e.classifyNetError(ctx, err)
		return nil, nil, classify, err
	}
	b, _ := io.ReadAll(resp.Body)
	// 注意：调用者仍负责 resp.Body 的关闭，本处只是预读。
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
