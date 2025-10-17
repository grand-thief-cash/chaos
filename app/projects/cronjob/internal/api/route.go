package api

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
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
				fmt.Sscanf(idParam, "%d", &id)
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
				taskMgmtCtrl.updateStatus(w, r, getID(r), "ENABLED")
			})
			r.Patch("/{id}/disable", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.updateStatus(w, r, getID(r), "DISABLED")
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
				fmt.Sscanf(idParam, "%d", &id)
				return id
			}
			r.Get("/{id}", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.getRun(w, r, getRunID(r))
			})
			r.Post("/{id}/cancel", func(w http.ResponseWriter, r *http.Request) {
				taskMgmtCtrl.cancelRun(w, r, getRunID(r))
			})
		})

		return nil
	})

}
