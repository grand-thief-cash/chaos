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

// v2 unified route registration for phoenixA.
func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {

		// ====== Securities (replaces stock_zh_a_list) ======
		securityCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_SECURITY)
		if err != nil {
			return err
		}
		securityCtrl := securityCtrlComp.(*controller.SecurityController)

		r.Route("/api/v2/securities", func(r chi.Router) {
			r.Get("/", securityCtrl.List)
			r.Post("/upsert", securityCtrl.BatchUpsert)
			r.Get("/count", securityCtrl.Count)
			r.Delete("/all", securityCtrl.DeleteAll)
			r.Get("/{symbol}", func(w http.ResponseWriter, req *http.Request) {
				securityCtrl.Get(w, req, chi.URLParam(req, "symbol"))
			})
		})

		// ====== Bars (replaces stock_zh_a_hist) ======
		barsCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_BARS)
		if err != nil {
			return err
		}
		barsCtrl := barsCtrlComp.(*controller.BarsController)

		r.Route("/api/v2/bars/{asset_type}/{market}", func(r chi.Router) {
			r.Get("/", barsCtrl.Query)
			r.Post("/upsert", barsCtrl.Upsert)
			r.Get("/last_update", barsCtrl.GetLastUpdate)
		})

		// ====== Taxonomy (replaces market_category + category_stock_map) ======
		taxonomyCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_TAXONOMY)
		if err != nil {
			return err
		}
		taxonomyCtrl := taxonomyCtrlComp.(*controller.TaxonomyController)

		r.Route("/api/v2/taxonomy", func(r chi.Router) {
			r.Get("/by_security/{symbol}", taxonomyCtrl.ListMappingsBySymbol)
			r.Route("/{source}", func(r chi.Router) {
				r.Get("/categories", taxonomyCtrl.ListCategories)
				r.Post("/categories/upsert", taxonomyCtrl.BatchUpsertCategories)
				r.Get("/categories/{code}", taxonomyCtrl.GetCategory)
				r.Delete("/categories/{code}", taxonomyCtrl.DeleteCategory)
				r.Post("/mapping/upsert", taxonomyCtrl.BatchUpsertMappings)
				r.Post("/mapping/replace/by_symbol", taxonomyCtrl.ReplaceCategoriesForSymbols)
				r.Post("/mapping/replace/by_category", taxonomyCtrl.ReplaceStocksForCategories)
				r.Get("/mapping/by_category/{categoryCode}", taxonomyCtrl.ListMappingsByCategory)
				r.Delete("/mapping/{categoryCode}/{symbol}", taxonomyCtrl.DeleteMapping)
			})
		})

		// ====== Strategy Run (unchanged) ======
		strategyRunCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_STRATEGY_RUN)
		if err != nil {
			return err
		}
		strategyRunCtrl := strategyRunCtrlComp.(*controller.StrategyRunController)

		r.Route("/api/v1/strategy/run", func(r chi.Router) {
			r.Get("/list", strategyRunCtrl.ListSummaries)
			r.Post("/summary/upsert", strategyRunCtrl.UpsertSummary)
			r.Post("/artifact/upsert", strategyRunCtrl.UpsertArtifacts)
			r.Get("/{run_id}", func(w http.ResponseWriter, req *http.Request) {
				strategyRunCtrl.GetSummary(w, req, chi.URLParam(req, "run_id"))
			})
			r.Get("/{run_id}/artifacts", func(w http.ResponseWriter, req *http.Request) {
				strategyRunCtrl.ListArtifacts(w, req, chi.URLParam(req, "run_id"))
			})
		})

		// ====== Legacy v1 routes (backward compatible - proxied to v2 logic) ======
		// Securities legacy routes
		r.Route("/api/v1/stock/list", func(r chi.Router) {
			r.Get("/", securityCtrl.List)
			r.Post("/", func(w http.ResponseWriter, req *http.Request) {
				securityCtrl.BatchUpsert(w, req)
			})
			r.Get("/count", securityCtrl.Count)
			r.Post("/batch_upsert", securityCtrl.BatchUpsert)
			r.Delete("/all", securityCtrl.DeleteAll)
			r.Get("/listFiltered", securityCtrl.List)
			r.Get("/countFiltered", securityCtrl.Count)
			r.Get("/{code}", func(w http.ResponseWriter, req *http.Request) {
				securityCtrl.Get(w, req, chi.URLParam(req, "code"))
			})
		})

		// Bars legacy routes
		r.Route("/api/v1/stock/hist", func(r chi.Router) {
			r.Post("/upsert", barsCtrl.Upsert)
			r.Get("/last_update", barsCtrl.GetLastUpdate)
			r.Get("/get_data", barsCtrl.Query)
		})

		// Taxonomy legacy routes
		r.Route("/api/v1/market_category", func(r chi.Router) {
			r.Post("/upsert/{source}", taxonomyCtrl.BatchUpsertCategories)
			r.Get("/{source}", taxonomyCtrl.ListCategories)
		})
		r.Route("/api/v1/category_stock_map", func(r chi.Router) {
			r.Post("/upsert", taxonomyCtrl.BatchUpsertMappings)
			r.Post("/replace/by_stock", func(w http.ResponseWriter, req *http.Request) {
				taxonomyCtrl.ReplaceCategoriesForSymbols(w, req)
			})
			r.Post("/replace/by_category", func(w http.ResponseWriter, req *http.Request) {
				taxonomyCtrl.ReplaceStocksForCategories(w, req)
			})
		})

		// OpenAPI spec endpoint
		r.Get("/openapi.yaml", func(w http.ResponseWriter, req *http.Request) {
			candidates := []string{
				"openapi.yaml",
				filepath.Join("app", "projects", "phoenixA", "openapi.yaml"),
			}
			var data []byte
			for _, p := range candidates {
				if _, stErr := os.Stat(p); stErr == nil {
					data, _ = os.ReadFile(p)
					break
				}
			}
			if data == nil {
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
