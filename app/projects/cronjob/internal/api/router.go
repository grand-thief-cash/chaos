package api

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

type TaskDaoIface interface {
	Create(context.Context, *model.Task) error
	Get(context.Context, int64) (*model.Task, error)
	ListEnabled(context.Context) ([]*model.Task, error)
	UpdateCronAndMeta(context.Context, *model.Task) error
	UpdateStatus(context.Context, int64, string) error
	SoftDelete(context.Context, int64) error
}

type RunDaoIface interface {
	CreateScheduled(context.Context, *model.TaskRun) error
	Get(context.Context, int64) (*model.TaskRun, error)
	ListByTask(context.Context, int64, int) ([]*model.TaskRun, error)
	MarkCanceled(context.Context, int64) error
}

type ExecutorIface interface {
	Enqueue(*model.TaskRun)
	ActiveCount(taskID int64) int
	CancelRun(id int64)
}

// Dependencies injected into handlers
// Sched 保留占位未来需要

type Dependencies struct {
	TaskRepo TaskDaoIface
	RunRepo  RunDaoIface
	Exec     ExecutorIface
	Sched    interface{}
	Version  string
}

func NewRouter(dep Dependencies) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})
	mux.HandleFunc("/api/v1/version", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(dep.Version))
	})

	// tasks collection
	mux.HandleFunc("/api/v1/tasks", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			createTask(w, r, dep)
			return
		}
		if r.Method == http.MethodGet {
			listTasks(w, r, dep)
			return
		}
		http.NotFound(w, r)
	})

	// tasks detail and sub-resources
	mux.HandleFunc("/api/v1/tasks/", func(w http.ResponseWriter, r *http.Request) {
		parts := pathParts(r.URL.Path)
		// /api/v1/tasks/{id}
		if len(parts) < 4 {
			http.NotFound(w, r)
			return
		}
		id, err := strconv.ParseInt(parts[3], 10, 64)
		if err != nil {
			writeErr(w, 400, "INVALID_ID")
			return
		}
		if len(parts) == 4 {
			switch r.Method {
			case http.MethodGet:
				getTask(w, r, dep, id)
			case http.MethodPut, http.MethodPatch:
				updateTask(w, r, dep, id)
			case http.MethodDelete:
				deleteTask(w, r, dep, id)
			default:
				http.NotFound(w, r)
			}
			return
		}
		if len(parts) == 5 {
			action := parts[4]
			if action == "enable" && r.Method == http.MethodPatch {
				dep.TaskRepo.UpdateStatus(r.Context(), id, "ENABLED")
				writeJSON(w, map[string]string{"status": "ENABLED"})
				return
			}
			if action == "disable" && r.Method == http.MethodPatch {
				dep.TaskRepo.UpdateStatus(r.Context(), id, "DISABLED")
				writeJSON(w, map[string]string{"status": "DISABLED"})
				return
			}
			if action == "trigger" && r.Method == http.MethodPost {
				triggerTask(w, r, dep, id)
				return
			}
			if action == "runs" && r.Method == http.MethodGet {
				listRuns(w, r, dep, id)
				return
			}
		}
		http.NotFound(w, r)
	})

	// runs detail & cancel: /api/v1/runs/{id} (GET) and /api/v1/runs/{id}/cancel (POST)
	mux.HandleFunc("/api/v1/runs/", func(w http.ResponseWriter, r *http.Request) {
		parts := pathParts(r.URL.Path)
		if len(parts) < 4 {
			http.NotFound(w, r)
			return
		}
		runID, err := strconv.ParseInt(parts[3], 10, 64)
		if err != nil {
			writeErr(w, 400, "INVALID_ID")
			return
		}
		if len(parts) == 4 {
			if r.Method == http.MethodGet {
				getRun(w, r, dep, runID)
				return
			}
			http.NotFound(w, r)
			return
		}
		if len(parts) == 5 && parts[4] == "cancel" && r.Method == http.MethodPost {
			dep.Exec.CancelRun(runID)
			_ = dep.RunRepo.MarkCanceled(r.Context(), runID)
			writeJSON(w, map[string]any{"run_id": runID, "status": "CANCELED"})
			return
		}
		http.NotFound(w, r)
	})

	return mux
}

func createTask(w http.ResponseWriter, r *http.Request, dep Dependencies) {
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
	if err := dep.TaskRepo.Create(r.Context(), t); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	writeJSON(w, map[string]any{"id": t.ID, "name": t.Name})
}

func listTasks(w http.ResponseWriter, r *http.Request, dep Dependencies) {
	list, _ := dep.TaskRepo.ListEnabled(r.Context())
	writeJSON(w, list)
}

func getTask(w http.ResponseWriter, r *http.Request, dep Dependencies, id int64) {
	t, err := dep.TaskRepo.Get(r.Context(), id)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	writeJSON(w, t)
}

func updateTask(w http.ResponseWriter, r *http.Request, dep Dependencies, id int64) {
	var req struct {
		Description string
		CronExpr    string
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, "INVALID_JSON")
		return
	}
	t, err := dep.TaskRepo.Get(r.Context(), id)
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
	if err := dep.TaskRepo.UpdateCronAndMeta(r.Context(), t); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	writeJSON(w, map[string]any{"updated": true})
}

func deleteTask(w http.ResponseWriter, r *http.Request, dep Dependencies, id int64) {
	_ = dep.TaskRepo.SoftDelete(r.Context(), id)
	writeJSON(w, map[string]any{"deleted": true})
}

func triggerTask(w http.ResponseWriter, r *http.Request, dep Dependencies, id int64) {
	t, err := dep.TaskRepo.Get(r.Context(), id)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	// concurrency skip policy enforcement for manual trigger
	if t.ConcurrencyPolicy == model.ConcurrencySkip && t.MaxConcurrency > 0 && dep.Exec.ActiveCount(t.ID) >= t.MaxConcurrency {
		writeErr(w, 409, "CONCURRENCY_LIMIT")
		return
	}
	run := &model.TaskRun{TaskID: t.ID, ScheduledTime: time.Now().UTC().Truncate(time.Second), Status: model.RunStatusScheduled, Attempt: 1}
	if err := dep.RunRepo.CreateScheduled(r.Context(), run); err != nil {
		writeErr(w, 500, "INTERNAL")
		return
	}
	dep.Exec.Enqueue(run)
	writeJSON(w, map[string]any{"run_id": run.ID})
}

func listRuns(w http.ResponseWriter, r *http.Request, dep Dependencies, taskID int64) {
	list, _ := dep.RunRepo.ListByTask(r.Context(), taskID, 50)
	writeJSON(w, list)
}

func getRun(w http.ResponseWriter, r *http.Request, dep Dependencies, runID int64) {
	run, err := dep.RunRepo.Get(r.Context(), runID)
	if err != nil {
		writeErr(w, 404, "NOT_FOUND")
		return
	}
	writeJSON(w, run)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
func writeErr(w http.ResponseWriter, code int, msg string) {
	w.WriteHeader(code)
	writeJSON(w, map[string]string{"error": msg})
}

func pathParts(p string) []string {
	var r []string
	for _, seg := range strings.Split(p, "/") {
		if seg != "" {
			r = append(r, seg)
		}
	}
	return r
}
