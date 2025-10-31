package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		compTaskMgmtCtrl, err := c.Resolve(bizConsts.COMP_CTRL_TASK_MGMT)
		if err != nil {
			return err
		}
		taskMgmtCtrl, ok := compTaskMgmtCtrl.(*TaskMgmtController)
		if !ok {
			return fmt.Errorf("task_mgmt_ctrl type assertion failed")
		}

		// 路由分组
		r.Route("/api/v1/tasks", func(r chi.Router) {
			r.Get("/", taskMgmtCtrl.listTasks)
			r.Post("/", taskMgmtCtrl.createTask)

			getID := func(r *http.Request) int64 {
				idParam := chi.URLParam(r, "id")
				var id int64
				_, _ = fmt.Sscanf(idParam, "%d", &id)
				return id
			}

			// 基础资源路由
			r.Get("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.getTask(w, r, getID(r))
			})
			r.Put("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.updateTask(w, r, getID(r))
			})
			r.Patch("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.updateTask(w, r, getID(r))
			})
			r.Delete("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.deleteTask(w, r, getID(r))
			})

			// 子资源 / 操作 路由（显式写出，避免嵌套 Route 造成 /{id} 匹配被覆盖）
			r.Patch("/{id}/enable", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.updateStatus(w, r, getID(r), bizConsts.ENABLED)
			})
			r.Patch("/{id}/disable", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.updateStatus(w, r, getID(r), bizConsts.DISABLED)
			})
			r.Post("/{id}/trigger", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.triggerTask(w, r, getID(r))
			})
			r.Get("/{id}/runs", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.listRuns(w, r, getID(r))
			})
		})

		// runs 资源: 同样避免嵌套路由遮蔽 /{id}
		r.Route("/api/v1/runs", func(r chi.Router) {
			getRunID := func(r *http.Request) int64 {
				idParam := chi.URLParam(r, "id")
				var id int64
				_, _ = fmt.Sscanf(idParam, "%d", &id)
				return id
			}
			r.Get("/active", func(w http.ResponseWriter, r *http.Request) { // list active pending runs
				taskMgmtCtrl.listActiveRuns(w, r)
			})
			r.Get("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.getRun(w, r, getRunID(r))
			})
			r.Get("/{id}/progress", func(w http.ResponseWriter, r *http.Request) { // ephemeral progress
				taskMgmtCtrl.getRunProgress(w, r, getRunID(r))
			})
			r.Post("/{id}/progress", func(w http.ResponseWriter, r *http.Request) { // update ephemeral progress
				taskMgmtCtrl.setRunProgress(w, r, getRunID(r))
			})
			r.Post("/{id}/cancel", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.cancelRun(w, r, getRunID(r))
			})
			r.Post("/{id}/callback", func(w http.ResponseWriter, r *http.Request) { // finalize async
				taskMgmtCtrl.finalizeCallback(w, r, getRunID(r))
			})
		})

		// management / cache ops
		r.Post("/api/v1/tasks/cache/refresh", func(w http.ResponseWriter, r *http.Request) { taskMgmtCtrl.refreshCache(w, r) })

		return nil
	})

}

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
