package api

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// Unified route registration combining task + run controllers.
func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		// resolve controllers
		compTask, err := c.Resolve(bizConsts.COMP_CTRL_TASK_MGMT)
		if err != nil {
			return err
		}
		taskCtrl, ok := compTask.(*TaskMgmtController)
		if !ok {
			return fmt.Errorf("task_mgmt_ctrl type assertion failed")
		}
		compRun, err := c.Resolve(bizConsts.COMP_CTRL_RUN_MGMT)
		if err != nil {
			return err
		}
		runCtrl, ok := compRun.(*RunMgmtController)
		if !ok {
			return fmt.Errorf("run_mgmt_ctrl type assertion failed")
		}

		// Task routes
		r.Route("/api/v1/tasks", func(r chi.Router) {
			getTaskID := func(r *http.Request) int64 {
				var id int64
				_, _ = fmt.Sscanf(chi.URLParam(r, "id"), "%d", &id)
				return id
			}
			r.Get("/", taskCtrl.listTasks)
			r.Post("/", taskCtrl.createTask)
			r.Get("/{id}", func(w http.ResponseWriter, req *http.Request) { taskCtrl.getTask(w, req, getTaskID(req)) })
			r.Put("/{id}", func(w http.ResponseWriter, req *http.Request) { taskCtrl.updateTask(w, req, getTaskID(req)) })
			r.Patch("/{id}", func(w http.ResponseWriter, req *http.Request) { taskCtrl.updateTask(w, req, getTaskID(req)) })
			r.Delete("/{id}", func(w http.ResponseWriter, req *http.Request) { taskCtrl.deleteTask(w, req, getTaskID(req)) })
			r.Patch("/{id}/enable", func(w http.ResponseWriter, req *http.Request) {
				taskCtrl.updateStatus(w, req, getTaskID(req), bizConsts.ENABLED)
			})
			r.Patch("/{id}/disable", func(w http.ResponseWriter, req *http.Request) {
				taskCtrl.updateStatus(w, req, getTaskID(req), bizConsts.DISABLED)
			})
			r.Post("/{id}/trigger", func(w http.ResponseWriter, req *http.Request) { taskCtrl.triggerTask(w, req, getTaskID(req)) })
			// migrated run listing
			r.Get("/{id}/runs", func(w http.ResponseWriter, req *http.Request) { runCtrl.listRunsByTask(w, req, getTaskID(req)) })
			r.Get("/{id}/runs/stats", func(w http.ResponseWriter, req *http.Request) { runCtrl.taskRunStats(w, req, getTaskID(req)) })
		})

		// Run routes
		r.Route("/api/v1/runs", func(r chi.Router) {
			getRunID := func(r *http.Request) int64 {
				var id int64
				_, _ = fmt.Sscanf(chi.URLParam(r, "id"), "%d", &id)
				return id
			}
			// list all in-memory progress first
			r.Get("/progress", runCtrl.listAllRunProgress)
			r.Get("/active", runCtrl.listActiveRuns)
			r.Get("/summary", runCtrl.summaryRuns)
			r.Post("/cleanup", runCtrl.cleanupRuns)
			r.Get("/{id}", func(w http.ResponseWriter, req *http.Request) { runCtrl.getRun(w, req, getRunID(req)) })
			r.Post("/{id}/cancel", func(w http.ResponseWriter, req *http.Request) { runCtrl.cancelRun(w, req, getRunID(req)) })
			r.Get("/{id}/progress", func(w http.ResponseWriter, req *http.Request) { runCtrl.getRunProgress(w, req, getRunID(req)) })
			r.Post("/{id}/progress", func(w http.ResponseWriter, req *http.Request) { runCtrl.setRunProgress(w, req, getRunID(req)) })
			r.Post("/{id}/callback", func(w http.ResponseWriter, req *http.Request) { runCtrl.finalizeCallback(w, req, getRunID(req)) })
		})

		// management/cache ops
		r.Post("/api/v1/tasks/cache/refresh", func(w http.ResponseWriter, req *http.Request) { taskCtrl.refreshCache(w, req) })
		return nil
	})
}
