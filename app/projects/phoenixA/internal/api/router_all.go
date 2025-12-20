package api

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
)

// Unified route registration for phoenixA.
func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		comp, err := c.Resolve(bizConsts.COMP_CTRL_STOCK_ZH_A_LIST)
		if err != nil {
			return err
		}
		stockZhAListController, ok := comp.(*StockZhAListController)
		if !ok {
			return fmt.Errorf("stock_zh_a_list_ctrl type assertion failed")
		}

		// Data-platform style base URI: /api/v1/{market}/{resource}
		r.Route("/api/v1/zh/stock_list", func(r chi.Router) {
			r.Get("/", stockZhAListController.list)
			r.Post("/", stockZhAListController.create)
			r.Get("/count", stockZhAListController.count)
			r.Post("/batch_upsert", stockZhAListController.batchUpsert)
			r.Delete("/all", stockZhAListController.deleteAll)

			r.Get("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListController.get(w, req, chi.URLParam(req, "code"))
			})
			r.Put("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListController.update(w, req, chi.URLParam(req, "code"))
			})
			r.Patch("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListController.update(w, req, chi.URLParam(req, "code"))
			})
		})
		return nil
	})
}
