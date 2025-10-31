package api

import (
	"context"
	"encoding/json"
	"net/http"

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
	CancelRun(ctx context.Context, id int64)
}

// Dependencies injected into handlers
// Sched 保留占位未来需要

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
func writeErr(w http.ResponseWriter, code int, msg string) {
	w.WriteHeader(code)
	writeJSON(w, map[string]string{"error": msg})
}
