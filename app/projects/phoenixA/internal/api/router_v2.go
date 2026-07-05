package api

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/buffer"
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
			r.Get("/{security_id}", func(w http.ResponseWriter, req *http.Request) {
				securityCtrl.Get(w, req, chi.URLParam(req, "security_id"))
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
			r.Get("/by_security/{security_id}", taxonomyCtrl.ListMappingsBySecurity)
			r.Route("/{source}/{taxonomy}", func(r chi.Router) {
				// Mapping endpoints (id-keyed; no market in path)
				r.Post("/mapping/upsert", taxonomyCtrl.BatchUpsertMappings)
				r.Post("/mapping/replace/by_security", taxonomyCtrl.ReplaceCategoriesForSecurities)
				r.Post("/mapping/replace/by_category", taxonomyCtrl.ReplaceSecuritiesForCategories)
				r.Get("/mapping/by_category/{category_id}", taxonomyCtrl.ListMappingsByCategory)
				r.Delete("/mapping/{category_id}/{security_id}", taxonomyCtrl.DeleteMapping)

				r.Route("/{market}", func(r chi.Router) {
					// Categories (natural-key base table, unchanged)
					r.Get("/categories", taxonomyCtrl.ListCategories)
					r.Post("/categories/upsert", taxonomyCtrl.BatchUpsertCategories)
					r.Get("/categories/{code}", taxonomyCtrl.GetCategory)
					r.Delete("/categories/{code}", taxonomyCtrl.DeleteCategory)

					// Mapping sync (single-table SELECT DISTINCT, no JOIN — refactor §2.3)
					r.Post("/mapping/sync_from_constituents", taxonomyCtrl.SyncMappingsFromConstituents)

					// Industry Constituents (body carries SDK natural keys; phoenixA resolves to ids)
					r.Post("/industry-constituents/upsert", taxonomyCtrl.BatchUpsertConstituents)
					r.Get("/industry-constituents/by_category/{category_id}", taxonomyCtrl.ListConstituentsByCategory)
					r.Get("/industry-constituents/by_security/{security_id}", taxonomyCtrl.ListConstituentsBySecurity)

					// Industry Weights
					r.Post("/industry-weights/upsert", taxonomyCtrl.BatchUpsertWeights)
					r.Get("/industry-weights/{category_id}", taxonomyCtrl.ListWeightsByCategoryAndDate)

					// Industry Daily
					r.Post("/industry-daily/upsert", taxonomyCtrl.BatchUpsertIndustryDaily)
					r.Get("/industry-daily", taxonomyCtrl.QueryIndustryDaily)
				})
			})
		})

		// ====== Financial Statements ======
		finStmtCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_FINANCIAL_STMT)
		if err != nil {
			return err
		}
		finStmtCtrl := finStmtCtrlComp.(*controller.FinancialStatementController)

		r.Route("/api/v2/financial/{source}/{statement_type}", func(r chi.Router) {
			r.Post("/upsert", finStmtCtrl.BatchUpsert)
			r.Get("/", finStmtCtrl.Query)
		})

		// ====== Corporate Actions ======
		corpActionCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_CORP_ACTION)
		if err != nil {
			return err
		}
		corpActionCtrl := corpActionCtrlComp.(*controller.CorporateActionController)

		r.Route("/api/v2/corporate-action/{source}/{action_type}", func(r chi.Router) {
			r.Post("/upsert", corpActionCtrl.BatchUpsert)
			r.Get("/", corpActionCtrl.Query)
		})

		// ====== Adjust Factors ======
		adjustFactorCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_ADJUST_FACTOR)
		if err != nil {
			return err
		}
		adjustFactorCtrl := adjustFactorCtrlComp.(*controller.AdjustFactorController)

		r.Route("/api/v2/adjust-factors/{source}", func(r chi.Router) {
			r.Post("/upsert", adjustFactorCtrl.BatchUpsert)
			r.Get("/", adjustFactorCtrl.Query)
		})

		// ====== Long Hu Bang ======
		longHuBangCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_LONG_HU_BANG)
		if err != nil {
			return err
		}
		longHuBangCtrl := longHuBangCtrlComp.(*controller.LongHuBangController)

		r.Route("/api/v2/long-hu-bang/{source}", func(r chi.Router) {
			r.Post("/upsert", longHuBangCtrl.BatchUpsert)
			r.Get("/", longHuBangCtrl.Query)
		})

		// ====== Equity Structure ======
		equityStructCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_EQUITY_STRUCTURE)
		if err != nil {
			return err
		}
		equityStructCtrl := equityStructCtrlComp.(*controller.EquityStructureController)

		r.Route("/api/v2/equity-structure/{source}", func(r chi.Router) {
			r.Post("/upsert", equityStructCtrl.BatchUpsert)
			r.Get("/", equityStructCtrl.Query)
		})

		// ====== Schema Discovery ======
		schemaCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_SCHEMA)
		if err != nil {
			return err
		}
		schemaCtrl := schemaCtrlComp.(*controller.SchemaController)

		r.Route("/api/v2/schema", func(r chi.Router) {
			r.Get("/domains", schemaCtrl.ListDomains)
			r.Get("/types", schemaCtrl.ListTypes)
			r.Get("/fields", schemaCtrl.DiscoverFields)
			r.Get("/overview", schemaCtrl.Overview)
		})

		// ====== Data Catalog ======
		catalogCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_CATALOG)
		if err != nil {
			return err
		}
		catalogCtrl := catalogCtrlComp.(*controller.CatalogController)

		// ====== Field Dictionary Discovery (Phase 2) ======
		fieldDictCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_FIELD_DICTIONARY)
		if err != nil {
			return err
		}
		fieldDictCtrl := fieldDictCtrlComp.(*controller.FieldDictionaryController)

		// ====== Field Coverage Observation (Phase 4 #3) ======
		fieldCoverageCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_FIELD_COVERAGE)
		if err != nil {
			return err
		}
		fieldCoverageCtrl := fieldCoverageCtrlComp.(*controller.FieldCoverageController)

		r.Route("/api/v2/catalog", func(r chi.Router) {
			r.Get("/overview", catalogCtrl.Overview)
			r.Get("/tables", catalogCtrl.ListTables)
			r.Get("/tables/{schema}/{table}", catalogCtrl.GetTableDetail)
			r.Get("/storage", catalogCtrl.StorageInfo)
			r.Get("/graph", catalogCtrl.GraphCatalog)
			r.Get("/data-dictionary", catalogCtrl.DataDictionary)
			r.Get("/business-overview", catalogCtrl.BusinessOverview)
			r.Get("/capabilities", catalogCtrl.Capabilities)
			r.Get("/securities/{security_id}/datasets/summary", catalogCtrl.GetSecurityCoverage)

			// Field dictionary discovery APIs (Phase 2 of AmazingData field
			// discovery design). Backed by data_dataset_dictionary /
			// data_field_dictionary / data_enum_dictionary.
			r.Get("/datasets", fieldDictCtrl.ListDatasets)
			r.Get("/datasets/{dataset}/fields", fieldDictCtrl.DiscoverFields)
			r.Get("/enums/{enum_name}", fieldDictCtrl.GetEnum)

			// Field coverage observation APIs (Phase 4 #3). Scans observed
			// data_json keys and flags SDK-added fields the dictionary hasn't
			// caught up with.
			r.Route("/field-coverage", func(r chi.Router) {
				r.Post("/scan", fieldCoverageCtrl.Scan)
				r.Get("/", fieldCoverageCtrl.List)
			})
		})

		// ====== Knowledge Graph (KG) ======
		kgCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_KG)
		if err != nil {
			return err
		}
		kgCtrl := kgCtrlComp.(*controller.KgController)

		r.Route("/api/v1/kg", func(r chi.Router) {
			// Documents
			r.Post("/documents", kgCtrl.CreateDocument)
			r.Get("/documents", kgCtrl.ListDocuments)
			r.Get("/documents/{doc_id}", func(w http.ResponseWriter, req *http.Request) {
				kgCtrl.GetDocument(w, req, chi.URLParam(req, "doc_id"))
			})
			r.Put("/documents/{doc_id}", func(w http.ResponseWriter, req *http.Request) {
				kgCtrl.UpdateDocument(w, req, chi.URLParam(req, "doc_id"))
			})

			// Extractions
			r.Post("/extractions", kgCtrl.CreateExtraction)
			r.Get("/extractions", kgCtrl.ListExtractions)
			r.Get("/extractions/{id}", func(w http.ResponseWriter, req *http.Request) {
				kgCtrl.GetExtraction(w, req, chi.URLParam(req, "id"))
			})

			// Events
			r.Post("/events", kgCtrl.CreateEvent)
			r.Get("/events", kgCtrl.ListEvents)
			r.Get("/events/recent", kgCtrl.ListRecentEvents)
			r.Get("/events/{id}", func(w http.ResponseWriter, req *http.Request) {
				kgCtrl.GetEvent(w, req, chi.URLParam(req, "id"))
			})
			r.Put("/events/{id}", func(w http.ResponseWriter, req *http.Request) {
				kgCtrl.UpdateEvent(w, req, chi.URLParam(req, "id"))
			})

			// Graph Ingestions
			r.Post("/graph-ingestions", kgCtrl.CreateGraphIngestion)

			// Daily Runs
			r.Post("/daily-runs", kgCtrl.CreateDailyRun)
			r.Get("/daily-runs", kgCtrl.ListDailyRuns)

			// Impact Logs
			r.Post("/impact-logs", kgCtrl.CreateImpactLog)
			r.Get("/impact-logs", kgCtrl.ListImpactLogs)
		})

		// ====== Graph (Neo4j) ======
		graphCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_GRAPH)
		if err == nil {
			graphCtrl := graphCtrlComp.(*controller.GraphController)

			r.Route("/api/v1/graph", func(r chi.Router) {
				// Cypher execution
				r.Post("/cypher", graphCtrl.RunCypher)
				r.Post("/cypher/write", graphCtrl.RunCypherWrite)

				// Node/Edge merge
				r.Post("/nodes/merge", graphCtrl.MergeNode)
				r.Post("/nodes/merge-batch", graphCtrl.MergeNodeBatch)
				r.Post("/edges/merge", graphCtrl.MergeEdge)
				r.Post("/edges/merge-batch", graphCtrl.MergeEdgeBatch)

				// Read queries
				r.Get("/search", graphCtrl.SearchNodes)
				r.Get("/stats", graphCtrl.GetGraphStats)
				r.Get("/company/{name}", func(w http.ResponseWriter, req *http.Request) {
					graphCtrl.GetCompanyFull(w, req, chi.URLParam(req, "name"))
				})
				r.Get("/company/{name}/chain", func(w http.ResponseWriter, req *http.Request) {
					graphCtrl.GetCompanyChain(w, req, chi.URLParam(req, "name"))
				})
				r.Get("/company/{name}/timeline", func(w http.ResponseWriter, req *http.Request) {
					graphCtrl.GetCompanyTimeline(w, req, chi.URLParam(req, "name"))
				})
				r.Get("/company/{name}/competitors", func(w http.ResponseWriter, req *http.Request) {
					graphCtrl.GetCompanyCompetitors(w, req, chi.URLParam(req, "name"))
				})
				r.Get("/event/{name}/impacts", func(w http.ResponseWriter, req *http.Request) {
					graphCtrl.GetEventImpacts(w, req, chi.URLParam(req, "name"))
				})

				// Schema management
				r.Post("/schema/ensure", graphCtrl.EnsureSchema)
			})
		}

		// ====== Legacy v1 routes (backward compatible - proxied to v2 logic) ======
		// Bars legacy routes
		r.Route("/api/v1/stock/hist", func(r chi.Router) {
			r.Post("/upsert", barsCtrl.Upsert)
			r.Get("/last_update", barsCtrl.GetLastUpdate)
			r.Get("/get_data", barsCtrl.Query)
		})

		// Legacy v1 taxonomy routes (market_category / category_stock_map) removed in
		// Phase 2 surrogate-key refactor — no caller (artemis uses /api/v2/taxonomy/*;
		// grep of /api/v1/(market_category|category_stock_map) hits only this file and
		// stale design docs). Per the "no legacy / no dual-track" principle (Phase 1
		// already removed /api/v1/stock/list/*).

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

		// ====== Write Buffer Stats ======
		bufMgrComp, err := c.Resolve(bizConsts.COMP_WRITE_BUFFER)
		if err == nil {
			bufMgr := bufMgrComp.(*buffer.WriteBufferManager)
			r.Get("/api/v2/buffer/stats", func(w http.ResponseWriter, req *http.Request) {
				stats := bufMgr.Stats()
				enabled := bufMgr.IsEnabled()
				resp := map[string]any{
					"enabled": enabled,
					"buffers": stats,
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusOK)
				enc := json.NewEncoder(w)
				_ = enc.Encode(resp)
			})
		}

		return nil
	})
}
