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
			r.Post("/upsert", stockZHAHistCtrl.BatchUpsert)
			r.Get("/last_update", stockZHAHistCtrl.GetStockLastUpdate)
			r.Get("/get_data", stockZHAHistCtrl.GetDailyByCodeDateRange)
		})

		// Market Category Routes
		marketCategoryCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_MARKET_CATEGORY)
		if err != nil {
			return err
		}
		marketCategoryCtrl := marketCategoryCtrlComp.(*controller.MarketCategoryController)

		r.Route("/api/v1/market_category", func(r chi.Router) {
			r.Post("/{source}", marketCategoryCtrl.Create)
			r.Post("/upsert/{source}", marketCategoryCtrl.BatchUpsert)
			r.Get("/{source}", marketCategoryCtrl.List)
			r.Route("/{source}/{code}", func(r chi.Router) {
				r.Get("/{source}", marketCategoryCtrl.Get)
				r.Put("/{source}", marketCategoryCtrl.Update)
				r.Delete("/{source}", marketCategoryCtrl.Delete)
			})
		})

		// Category Stock Map Routes
		categoryStockMapCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_CATEGORY_STOCK_MAP)
		if err != nil {
			return err
		}
		categoryStockMapCtrl := categoryStockMapCtrlComp.(*controller.CategoryStockMapController)

		r.Route("/api/v1/category_stock_map", func(r chi.Router) {
			r.Post("/", categoryStockMapCtrl.Create)
			r.Post("/upsert", categoryStockMapCtrl.BatchUpsert)
			// Replaces all categories for the given stocks (map[stock_code] -> []category_codes)
			r.Post("/replace/by_stock", categoryStockMapCtrl.ReplaceCategoriesForStocks)
			// Replaces all stocks for the given categories (map[category_code] -> []stock_codes)
			r.Post("/replace/by_category", categoryStockMapCtrl.ReplaceStocksForCategories)
			r.Delete("/{categoryCode}/{stockCode}", categoryStockMapCtrl.Delete)
			r.Get("/by_category/{categoryCode}", categoryStockMapCtrl.ListByCategory)
			r.Get("/by_stock/{stockCode}", categoryStockMapCtrl.ListByStock)
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
