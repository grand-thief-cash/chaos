package api

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		pocCtrlComp, err := c.Resolve("poc_ctrl")
		if err != nil {
			return err
		}
		pocCtrl, ok := pocCtrlComp.(*POCController)
		if !ok {
			return fmt.Errorf("task_mgmt_ctrl type assertion failed")
		}

		// 路由分组
		r.Route("/get_answer", func(r chi.Router) {
			r.Get("/", pocCtrl.giveAnswer)
			r.Get("/progress", pocCtrl.giveAnswerAndProgress)

			getID := func(r *http.Request) int64 {
				idParam := chi.URLParam(r, "id")
				var id int64
				_, _ = fmt.Sscanf(idParam, "%d", &id)
				return id
			}
			fmt.Println(getID)
		})
		return nil
	})

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
