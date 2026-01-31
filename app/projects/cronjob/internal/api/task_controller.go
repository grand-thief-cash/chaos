package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel/trace"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/service"
)

type TaskMgmtController struct {
	*core.BaseComponent
	TaskSvc  *service.TaskService        `infra:"dep:task_service"`
	RunSvc   *service.RunService         `infra:"dep:run_service"`
	Exec     *service.Executor           `infra:"dep:executor"`
	Sched    *service.Engine             `infra:"dep:scheduler_engine"`
	Progress *service.RunProgressManager `infra:"dep:run_progress_mgr"` // ephemeral progress store
}

func NewTaskMgmtController() *TaskMgmtController {
	return &TaskMgmtController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_TASK_MGMT, consts.COMPONENT_LOGGING)}
}

func (tmc *TaskMgmtController) createTask(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req struct {
		Name               string `json:"name"`
		Description        string `json:"description"`
		CronExpr           string `json:"cron_expr"`
		Timezone           string `json:"timezone"`
		ExecType           string `json:"exec_type"`
		HTTPMethod         string `json:"method"` // 修改 JSON tag 为 "method"
		TargetService      string `json:"target_service"`
		TargetPath         string `json:"target_path"`
		HeadersJSON        string `json:"headers_json"`
		BodyTemplate       string `json:"body_template"`
		RetryPolicyJSON    string `json:"retry_policy_json"`
		MaxConcurrency     int    `json:"max_concurrency"`
		ConcurrencyPolicy  string `json:"concurrency_policy"`
		CallbackMethod     string `json:"callback_method"`
		CallbackTimeoutSec int    `json:"callback_timeout_sec"`
		OverlapAction      string `json:"overlap_action"`
		FailureAction      string `json:"failure_action"`
		Status             string `json:"status"`
		Deleted            int    `json:"deleted"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		logging.Error(ctx, fmt.Sprintf("Task creation json decode failed: %v", err))
		writeErr(w, 400, err.Error())
		return
	}

	t := &model.Task{
		Name:               strings.TrimSpace(req.Name),
		Description:        req.Description,
		CronExpr:           model.NormalizeCron(req.CronExpr),
		Timezone:           defaultOr(req.Timezone, "UTC"),
		ExecType:           bizConsts.ExecType(req.ExecType),
		HTTPMethod:         strings.ToUpper(req.HTTPMethod),
		TargetService:      defaultOr(req.TargetService, "artemis"),
		TargetPath:         req.TargetPath,
		HeadersJSON:        defaultOr(req.HeadersJSON, bizConsts.DEFAULT_JSON_STR),
		BodyTemplate:       req.BodyTemplate,
		RetryPolicyJSON:    defaultOr(req.RetryPolicyJSON, bizConsts.DEFAULT_JSON_STR),
		MaxConcurrency:     defaultInt(req.MaxConcurrency, 1),
		ConcurrencyPolicy:  bizConsts.ConcurrencyPolicy(req.ConcurrencyPolicy),
		CallbackMethod:     defaultOr(req.CallbackMethod, "POST"),
		CallbackTimeoutSec: defaultInt(req.CallbackTimeoutSec, 300),
		OverlapAction:      bizConsts.OverlapAction(req.OverlapAction),
		FailureAction:      bizConsts.FailureAction(req.FailureAction),
		Status:             bizConsts.DISABLED,
		Version:            1,
		//CreatedAt:          time.Now().UTC(),
		//UpdatedAt:          time.Now().UTC(),
	}
	if t.CronExpr == "" || t.Name == "" || t.TargetService == "" || t.TargetPath == "" {
		writeErr(w, 400, "CronExpr/Name/TargetService/TargetPath cannot be empty")
		return
	}
	if err := tmc.TaskSvc.Create(r.Context(), t); err != nil {
		logging.Error(ctx, fmt.Sprintf("Task creation failed: %v", err))
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"id": t.ID, "name": t.Name})
}

func (tmc *TaskMgmtController) listTasks(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	filters := &model.TaskListFilters{}
	statusRaw := strings.TrimSpace(q.Get("status"))
	if statusRaw != "" {
		up := strings.ToUpper(statusRaw)
		if up == string(bizConsts.ENABLED) || up == string(bizConsts.DISABLED) {
			filters.Status = up
		} else {
			writeErr(w, 400, "invalid status")
			return
		}
	}
	if v := strings.TrimSpace(q.Get("name")); v != "" {
		filters.NameLike = v
	}
	if v := strings.TrimSpace(q.Get("description")); v != "" {
		filters.DescriptionLike = v
	}
	parseTime := func(key string) *time.Time {
		if s := strings.TrimSpace(q.Get(key)); s != "" {
			if t, err := time.Parse(time.RFC3339, s); err == nil {
				return &t
			}
		}
		return nil
	}
	filters.CreatedFrom = parseTime("created_from")
	filters.CreatedTo = parseTime("created_to")
	filters.UpdatedFrom = parseTime("updated_from")
	filters.UpdatedTo = parseTime("updated_to")
	limit := 50
	if v := strings.TrimSpace(q.Get("limit")); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i > 0 && i <= 500 {
			limit = i
		}
	}
	offset := 0
	if v := strings.TrimSpace(q.Get("offset")); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i >= 0 {
			offset = i
		}
	}
	list, err := tmc.TaskSvc.ListFiltered(r.Context(), filters, limit, offset)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	total, _ := tmc.TaskSvc.CountFiltered(r.Context(), filters)
	writeJSON(w, map[string]any{"items": list, "total": total, "limit": limit, "offset": offset})
}

func (tmc *TaskMgmtController) getTask(w http.ResponseWriter, r *http.Request, id int64) {
	t, err := tmc.TaskSvc.Get(r.Context(), id)
	if err != nil {
		logging.Error(r.Context(), fmt.Sprintf("Task get failed: %v", err))
		writeErr(w, 404, err.Error())
		return
	}
	writeJSON(w, t)
}

func (tmc *TaskMgmtController) updateTask(w http.ResponseWriter, r *http.Request, id int64) {
	ctx := r.Context()
	var req struct {
		Name               string `json:"name"`
		Description        string `json:"description"`
		CronExpr           string `json:"cron_expr"`
		Timezone           string `json:"timezone"`
		ExecType           string `json:"exec_type"`
		HTTPMethod         string `json:"method"` // 修改 JSON tag 为 "method"
		TargetService      string `json:"target_service"`
		TargetPath         string `json:"target_path"`
		HeadersJSON        string `json:"headers_json"`
		BodyTemplate       string `json:"body_template"`
		RetryPolicyJSON    string `json:"retry_policy_json"`
		MaxConcurrency     int    `json:"max_concurrency"`
		ConcurrencyPolicy  string `json:"concurrency_policy"`
		CallbackMethod     string `json:"callback_method"`
		CallbackTimeoutSec int    `json:"callback_timeout_sec"`
		OverlapAction      string `json:"overlap_action"`
		FailureAction      string `json:"failure_action"`
		Status             string `json:"status"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		logging.Error(ctx, fmt.Sprintf("Task update json decode failed: %v", err))
		writeErr(w, 400, err.Error())
		return
	}

	t, err := tmc.TaskSvc.Get(ctx, id)
	if err != nil {
		logging.Error(ctx, fmt.Sprintf("Task get failed: %v", err))
		writeErr(w, 404, err.Error())
		return
	}
	if req.Name != "" {
		t.Name = strings.TrimSpace(req.Name)
	}
	if req.ExecType != "" {
		t.ExecType = bizConsts.ExecType(req.ExecType)
	}
	if req.TargetService != "" {
		t.TargetService = req.TargetService
	}
	if req.TargetPath != "" {
		t.TargetPath = req.TargetPath
	}
	if req.HTTPMethod != "" {
		t.HTTPMethod = strings.ToUpper(req.HTTPMethod)
	}
	if req.Description != "" {
		t.Description = req.Description
	}
	if req.CronExpr != "" {
		t.CronExpr = model.NormalizeCron(req.CronExpr)
	}
	if req.MaxConcurrency >= 0 {
		t.MaxConcurrency = req.MaxConcurrency
	}
	if req.ConcurrencyPolicy != "" {
		t.ConcurrencyPolicy = bizConsts.ConcurrencyPolicy(req.ConcurrencyPolicy)
	}
	if req.OverlapAction != "" {
		t.OverlapAction = bizConsts.OverlapAction(req.OverlapAction)
	}
	if req.FailureAction != "" {
		t.FailureAction = bizConsts.FailureAction(req.FailureAction)
	}
	if req.BodyTemplate != "" {
		t.BodyTemplate = req.BodyTemplate
	}
	if req.HeadersJSON != "" {
		t.HeadersJSON = req.HeadersJSON
	}
	if req.CallbackMethod != "" {
		t.CallbackMethod = req.CallbackMethod
	}
	if req.CallbackTimeoutSec > 0 {
		t.CallbackTimeoutSec = req.CallbackTimeoutSec
	}
	if err := tmc.TaskSvc.UpdateCronAndMeta(ctx, t); err != nil {
		logging.Error(ctx, fmt.Sprintf("Task update failed: %v", err))
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"updated": true})
}

func (tmc *TaskMgmtController) deleteTask(w http.ResponseWriter, r *http.Request, id int64) {
	_ = tmc.TaskSvc.SoftDelete(r.Context(), id)
	writeJSON(w, map[string]any{"deleted": true})
}

func (tmc *TaskMgmtController) triggerTask(w http.ResponseWriter, r *http.Request, id int64) {
	// r.Context() used below for task retrieval and run creation
	t, err := tmc.TaskSvc.Get(r.Context(), id)
	if err != nil {
		logging.Error(r.Context(), fmt.Sprintf("Task triggered failed: %v", err))
		writeErr(w, 404, err.Error())
		return
	}
	// concurrency skip policy enforcement for manual trigger
	activeCount := tmc.Exec.ActiveCount(t.ID)
	maxConcurrent := t.MaxConcurrency
	if t.ConcurrencyPolicy == bizConsts.ConcurrencySkip && t.MaxConcurrency > 0 && activeCount >= maxConcurrent {
		errMsg := fmt.Sprintf("Task trigger concurrency limit reached: task_id=%d active=%d max=%d", t.ID, activeCount, maxConcurrent)
		logging.Error(r.Context(), errMsg)
		writeErr(w, 409, "CONCURRENCY_LIMIT")
		return
	}

	// FIX: 手动触发时，也需要从 Task 把快照字段填充到 TaskRun，否则 Executor 执行时会拿到空的 target/body
	// Use factory for consistency
	run := tmc.TaskSvc.CreateTaskRun(t, time.Now().UTC().Truncate(time.Second), 1)
	if run.TargetService == "" {
		logging.Error(r.Context(), fmt.Sprintf("triggerTask: target_service is empty for task_id=%d", t.ID))
		writeErr(w, 400, "target_service_empty")
		return
	}

	// Capture TraceID for async propagation
	span := trace.SpanFromContext(r.Context())
	if span.SpanContext().IsValid() {
		run.TraceID = span.SpanContext().TraceID().String()
	}

	if err := tmc.RunSvc.CreateScheduled(r.Context(), run); err != nil {
		logging.Error(r.Context(), fmt.Sprintf("Task trigger failed: %v", err))
		writeErr(w, 500, err.Error())
		return
	}
	logging.Info(r.Context(), fmt.Sprintf("Task trigger enqueueing: id=%d", t.ID))
	tmc.Exec.Enqueue(run)
	writeJSON(w, map[string]any{"run_id": run.ID})
}

func (tmc *TaskMgmtController) listRuns(w http.ResponseWriter, r *http.Request, taskID int64) {
	list, _ := tmc.RunSvc.ListByTask(r.Context(), taskID, 50)
	writeJSON(w, list)
}

func (tmc *TaskMgmtController) updateStatus(w http.ResponseWriter, r *http.Request, id int64, status bizConsts.TaskStatus) {
	err := tmc.TaskSvc.UpdateStatus(r.Context(), id, status)
	if err != nil {
		logging.Error(r.Context(), fmt.Sprintf("Task update status failed: %v", err))
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"updated": true})
}

func (tmc *TaskMgmtController) refreshCache(w http.ResponseWriter, r *http.Request) {
	if err := tmc.TaskSvc.Refresh(r.Context()); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"refreshed": true})
}

// defaultOr returns s if not empty, otherwise def
func defaultOr(s, def string) string {
	if strings.TrimSpace(s) != "" {
		return s
	}
	return def
}

// defaultInt returns i if not zero, otherwise def
func defaultInt(i, def int) int {
	if i != 0 {
		return i
	}
	return def
}
