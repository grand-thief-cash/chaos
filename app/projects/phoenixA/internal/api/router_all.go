package api

import (
	"net/http"
	"os"
	"path/filepath"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/controller"
)

// Unified route registration for phoenixA.
func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		stockZhAListComp, err := c.Resolve(bizConsts.COMP_CTRL_STOCK_ZH_A_LIST)
		if err != nil {
			return err
		}
		stockZhAListCtrl := stockZhAListComp.(*controller.StockZhAListController)

		r.Route("/api/v1/stock/list", func(r chi.Router) {
			r.Get("/", stockZhAListCtrl.List)
			r.Post("/", stockZhAListCtrl.Create)
			r.Get("/count", stockZhAListCtrl.Count)
			r.Post("/batch_upsert", stockZhAListCtrl.BatchUpsert)
			r.Delete("/all", stockZhAListCtrl.DeleteAll)

			r.Get("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListCtrl.Get(w, req, chi.URLParam(req, "code"))
			})
			r.Put("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListCtrl.Update(w, req, chi.URLParam(req, "code"))
			})
			r.Patch("/{code}", func(w http.ResponseWriter, req *http.Request) {
				stockZhAListCtrl.Update(w, req, chi.URLParam(req, "code"))
			})

			r.Get("/listFiltered", stockZhAListCtrl.List)
			r.Get("/countFiltered", stockZhAListCtrl.Count)
		})

		// History Data Routes
		stockZHAHistCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_STOCK_ZH_A_HIST)
		if err != nil {
			return err
		}
		stockZHAHistCtrl := stockZHAHistCtrlComp.(*controller.StockZhAHistController)

		r.Route("/api/v1/stock/hist", func(r chi.Router) {
			r.Post("/data", stockZHAHistCtrl.BatchSaveStockData)
			r.Get("/last_update", stockZHAHistCtrl.GetStockLastUpdate)
			r.Get("/range", stockZHAHistCtrl.GetDailyByCodeDateRange)
		})

		r.Get("/openapi.yaml", func(w http.ResponseWriter, req *http.Request) {
			// Try best-effort to find phoenixA/openapi.yaml based on current working directory.
			// In this repo, phoenixA is typically run with working dir app/projects/phoenixA.
			candidates := []string{
				"openapi.yaml",
				filepath.Join("app", "projects", "phoenixA", "openapi.yaml"),
				filepath.Join(".", "app", "projects", "phoenixA", "openapi.yaml"),
			}
			var data []byte
			var err error
			for _, p := range candidates {
				if _, stErr := os.Stat(p); stErr == nil {
					data, err = os.ReadFile(p)
					break
				}
			}
			if err != nil || data == nil {
				w.WriteHeader(http.StatusNotFound)
				_, _ = w.Write([]byte("openapi.yaml not found"))
				return
			}
			w.Header().Set("Content-Type", "application/yaml")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(data)
		})

		return nil
	})
}
