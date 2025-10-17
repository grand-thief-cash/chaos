package api

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type TaskMgmtController struct {
	*core.BaseComponent
	taskDao TaskDaoIface
	runDao  RunDaoIface
	Exec    ExecutorIface
	Sched   interface{}
}

func NewTaskMgmtController(taskDao dao.TaskDao, runDao dao.RunDao, exec ExecutorIface, Sched interface{}) *TaskMgmtController {
	return &TaskMgmtController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_TASK_MGMT, bizConsts.COMP_DAO_TASK,
			bizConsts.COMP_DAO_RUN, bizConsts.COMP_SVC_EXECUTOR, consts.COMPONENT_LOGGING),
		taskDao: taskDao,
		runDao:  runDao,
		Exec:    exec,
		Sched:   Sched,
	}
}

func (tmc *TaskMgmtController) createTask(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name           string `json:"name"`
		Description    string `json:"description"`
		CronExpr       string `json:"cron_expr"`
		ExecType       string `json:"exec_type"`
		HTTPMethod     string `json:"http_method"`
		TargetURL      string `json:"target_url"`
		TimeoutSeconds int    `json:"timeout_seconds"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, "Json Decode failed")
		return
	}
	t := &model.Task{
		Name:               strings.TrimSpace(req.Name),
		Description:        req.Description,
		CronExpr:           model.NormalizeCron(req.CronExpr),
		Timezone:           "UTC",
		ExecType:           model.ExecType(req.ExecType),
		HTTPMethod:         strings.ToUpper(req.HTTPMethod),
		TargetURL:          req.TargetURL,
		HeadersJSON:        "{}",
		BodyTemplate:       "",
		TimeoutSeconds:     10,
		RetryPolicyJSON:    "{}",
		MaxConcurrency:     1,
		ConcurrencyPolicy:  model.ConcurrencyQueue,
		MisfirePolicy:      "FIRE_NOW",
		CatchupLimit:       0,
		CallbackMethod:     "POST",
		CallbackTimeoutSec: 300,
		Status:             "ENABLED",
		Version:            1,
		CreatedAt:          time.Now().UTC(),
		UpdatedAt:          time.Now().UTC(),
	}
	if t.CronExpr == "" || t.Name == "" || t.TargetURL == "" {
		writeErr(w, 400, "INVALID_ARGUMENT")
		return
	}
	if err := tmc.taskDao.Create(r.Context(), t); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	writeJSON(w, map[string]any{"id": t.ID, "name": t.Name})
}

func (tmc *TaskMgmtController) listTasks(w http.ResponseWriter, r *http.Request) {
	list, _ := tmc.taskDao.ListEnabled(r.Context())
	writeJSON(w, list)
}

func (tmc *TaskMgmtController) getTask(w http.ResponseWriter, r *http.Request, id int64) {
	t, err := tmc.taskDao.Get(r.Context(), id)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	writeJSON(w, t)
}

func (tmc *TaskMgmtController) updateTask(w http.ResponseWriter, r *http.Request, id int64) {
	var req struct {
		Description string
		CronExpr    string
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, "INVALID_JSON")
		return
	}
	t, err := tmc.taskDao.Get(r.Context(), id)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	if req.Description != "" {
		t.Description = req.Description
	}
	if req.CronExpr != "" {
		t.CronExpr = model.NormalizeCron(req.CronExpr)
	}
	if err := tmc.taskDao.UpdateCronAndMeta(r.Context(), t); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	writeJSON(w, map[string]any{"updated": true})
}

func (tmc *TaskMgmtController) deleteTask(w http.ResponseWriter, r *http.Request, id int64) {
	_ = tmc.taskDao.SoftDelete(r.Context(), id)
	writeJSON(w, map[string]any{"deleted": true})
}

func (tmc *TaskMgmtController) triggerTask(w http.ResponseWriter, r *http.Request, id int64) {
	t, err := tmc.taskDao.Get(r.Context(), id)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	// concurrency skip policy enforcement for manual trigger
	if t.ConcurrencyPolicy == model.ConcurrencySkip && t.MaxConcurrency > 0 && tmc.Exec.ActiveCount(t.ID) >= t.MaxConcurrency {
		writeErr(w, 409, "CONCURRENCY_LIMIT")
		return
	}
	run := &model.TaskRun{TaskID: t.ID, ScheduledTime: time.Now().UTC().Truncate(time.Second), Status: model.RunStatusScheduled, Attempt: 1}
	if err := tmc.runDao.CreateScheduled(r.Context(), run); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	tmc.Exec.Enqueue(run)
	writeJSON(w, map[string]any{"run_id": run.ID})
}

func (tmc *TaskMgmtController) listRuns(w http.ResponseWriter, r *http.Request, taskID int64) {
	list, _ := tmc.runDao.ListByTask(r.Context(), taskID, 50)
	writeJSON(w, list)
}

func (tmc *TaskMgmtController) getRun(w http.ResponseWriter, r *http.Request, runID int64) {
	run, err := tmc.runDao.Get(r.Context(), runID)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	writeJSON(w, run)
}

func (tmc *TaskMgmtController) updateStatus(w http.ResponseWriter, r *http.Request, id int64, status string) {
	err := tmc.taskDao.UpdateStatus(r.Context(), id, status)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"updated": true})
}

func (tmc *TaskMgmtController) cancelRun(w http.ResponseWriter, r *http.Request, runID int64) {
	tmc.Exec.CancelRun(runID)
	writeJSON(w, map[string]any{"canceled": true})
}
