package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/service"
)

type TaskMgmtController struct {
	*core.BaseComponent
	TaskSvc *service.TaskService `infra:"dep:task_service"`
	RunSvc  *service.RunService  `infra:"dep:run_service"`
	Exec    *service.Executor    `infra:"dep:executor"`
	Sched   *service.Engine      `infra:"dep:scheduler_engine"`
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
		HTTPMethod         string `json:"http_method"`
		TargetURL          string `json:"target_url"`
		HeadersJSON        string `json:"headers_json"`
		BodyTemplate       string `json:"body_template"`
		TimeoutSeconds     int    `json:"timeout_seconds"`
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
		TargetURL:          req.TargetURL,
		HeadersJSON:        defaultOr(req.HeadersJSON, bizConsts.DEFAULT_JSON_STR),
		BodyTemplate:       req.BodyTemplate,
		TimeoutSeconds:     req.TimeoutSeconds,
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
	if t.CronExpr == "" || t.Name == "" || t.TargetURL == "" {
		writeErr(w, 400, "CronExpr/Name/TargetURL cannot be empty")
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
	list, _ := tmc.TaskSvc.ListEnabled(r.Context())
	writeJSON(w, list)
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
		HTTPMethod         string `json:"http_method"`
		TargetURL          string `json:"target_url"`
		HeadersJSON        string `json:"headers_json"`
		BodyTemplate       string `json:"body_template"`
		TimeoutSeconds     int    `json:"timeout_seconds"`
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
	if req.TargetURL != "" {
		t.TargetURL = req.TargetURL
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
	if req.TimeoutSeconds > 0 {
		t.TimeoutSeconds = req.TimeoutSeconds
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
	if t.ConcurrencyPolicy == bizConsts.ConcurrencySkip && t.MaxConcurrency > 0 && tmc.Exec.ActiveCount(t.ID) >= t.MaxConcurrency {
		writeErr(w, 409, "CONCURRENCY_LIMIT")
		return
	}
	run := &model.TaskRun{TaskID: t.ID, ScheduledTime: time.Now().UTC().Truncate(time.Second), Status: bizConsts.Scheduled, Attempt: 1}
	if err := tmc.RunSvc.CreateScheduled(r.Context(), run); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	tmc.Exec.Enqueue(run)
	writeJSON(w, map[string]any{"run_id": run.ID})
}

func (tmc *TaskMgmtController) listRuns(w http.ResponseWriter, r *http.Request, taskID int64) {
	list, _ := tmc.RunSvc.ListByTask(r.Context(), taskID, 50)
	writeJSON(w, list)
}

func (tmc *TaskMgmtController) getRun(w http.ResponseWriter, r *http.Request, runID int64) {
	run, err := tmc.RunSvc.Get(r.Context(), runID)
	if err != nil {
		logging.Error(r.Context(), fmt.Sprintf("Task get run failed: %v", err))
		writeErr(w, 404, err.Error())
		return
	}
	writeJSON(w, run)
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

func (tmc *TaskMgmtController) cancelRun(w http.ResponseWriter, r *http.Request, runID int64) {
	// use context for potential future logging/metrics
	_ = r.Context()
	tmc.Exec.CancelRun(runID)
	writeJSON(w, map[string]any{"canceled": true})
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
