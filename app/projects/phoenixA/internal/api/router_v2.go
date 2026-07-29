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
			r.Get("/search", securityCtrl.Search)
			r.Post("/upsert", securityCtrl.BatchUpsert)
			r.Get("/count", securityCtrl.Count)
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

		// ====== Capital-flow ODS datasets ======
		capitalFlowComp, err := c.Resolve(bizConsts.COMP_CTRL_CAPITAL_FLOW)
		if err != nil {
			return err
		}
		capitalFlowCtrl := capitalFlowComp.(*controller.CapitalFlowController)
		r.Route("/api/v2/capital-flows", func(r chi.Router) {
			r.Get("/margin-summary", capitalFlowCtrl.QueryMarginSummary)
			r.Get(
				"/margin-summary/last-update",
				capitalFlowCtrl.LastMarginSummaryDate,
			)
			r.Post("/margin-summary/upsert", capitalFlowCtrl.UpsertMarginSummary)
			r.Get("/hsgt", capitalFlowCtrl.QueryHSGT)
			r.Get("/hsgt/last-update", capitalFlowCtrl.LastHSGTDates)
			r.Post("/hsgt/upsert", capitalFlowCtrl.UpsertHSGT)
		})

		// ====== Option-market ODS datasets ======
		optionMarketDataComp, err := c.Resolve(
			bizConsts.COMP_CTRL_OPTION_MARKET_DATA,
		)
		if err != nil {
			return err
		}
		optionMarketDataCtrl := optionMarketDataComp.(*controller.OptionMarketDataController)
		r.Route("/api/v2/option-market-data", func(r chi.Router) {
			r.Get("/qvix", optionMarketDataCtrl.QueryOptionQVIX)
			r.Get("/qvix/last-update", optionMarketDataCtrl.LastOptionQVIXDates)
			r.Post("/qvix/upsert", optionMarketDataCtrl.UpsertOptionQVIX)
			r.Get("/daily-stats", optionMarketDataCtrl.QueryOptionDailyStats)
			r.Get(
				"/daily-stats/last-update",
				optionMarketDataCtrl.LastOptionDailyStatsDates,
			)
			r.Post(
				"/daily-stats/upsert",
				optionMarketDataCtrl.UpsertOptionDailyStats,
			)
		})

		// ====== Scalar market observations ======
		marketObservationComp, err := c.Resolve(
			bizConsts.COMP_CTRL_MARKET_OBSERVATION,
		)
		if err != nil {
			return err
		}
		marketObservationCtrl := marketObservationComp.(*controller.MarketObservationController)
		r.Route("/api/v2/market-observations/{source}", func(r chi.Router) {
			r.Get("/", marketObservationCtrl.Query)
			r.Get("/last-update", marketObservationCtrl.LastDates)
			r.Post("/upsert", marketObservationCtrl.Upsert)
		})

		securityEventComp, err := c.Resolve(bizConsts.COMP_CTRL_SECURITY_EVENT)
		if err != nil {
			return err
		}
		securityEventCtrl := securityEventComp.(*controller.SecurityEventController)
		r.Route("/api/v2/security-events/{source}/{event_type}", func(r chi.Router) {
			r.Post("/upsert", securityEventCtrl.BatchUpsert)
			r.Get("/last-update", securityEventCtrl.LastDatesBySecurityIDs)
			r.Get("/", securityEventCtrl.Query)
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

		// ====== Research Reports ======
		rrCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_RESEARCH_REPORT)
		if err != nil {
			return err
		}
		rrCtrl := rrCtrlComp.(*controller.ResearchReportController)

		r.Route("/api/v2/research-report/{source}", func(r chi.Router) {
			r.Post("/upsert", rrCtrl.BatchUpsert)
			r.Post("/{resource_id}/status", rrCtrl.UpdateStatus)
			r.Get("/last-update", rrCtrl.GetLastUpdate)
			r.Get("/max-publish-date", rrCtrl.GetMaxPublishDate)
			r.Get("/pending", rrCtrl.QueryPending)
			r.Get("/", rrCtrl.Query)
		})

		// ====== Feature Platform control plane ======
		featureCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_FEATURE)
		if err != nil {
			return err
		}
		featureCtrl := featureCtrlComp.(*controller.FeatureController)

		r.Route("/api/v2/features", func(r chi.Router) {
			r.Post("/registry/sync", featureCtrl.SyncRegistry)
			r.Get("/definitions", featureCtrl.ListDefinitions)
			r.Get("/definitions/{feature_code}", featureCtrl.GetDefinition)
			r.Get("/definitions/{feature_code}/lifecycle-events", featureCtrl.ListLifecycleEvents)
			r.Get("/versions/{version_id}", featureCtrl.GetVersion)
			r.Post("/definitions/{feature_code}/versions/{version}:publish", featureCtrl.PublishVersion)
			r.Post("/definitions/{feature_code}/versions/{version}:deprecate", featureCtrl.DeprecateVersion)
			r.Get("/lineage/{feature_code}", featureCtrl.Lineage)
			r.Get("/availability/{feature_code}", featureCtrl.Availability)

			r.Post("/runs", featureCtrl.CreateRun)
			r.Post("/runs:reconcile-stale", featureCtrl.ReconcileStaleRuns)
			r.Get("/runs", featureCtrl.ListRuns)
			r.Get("/runs/{run_id}", featureCtrl.GetRun)
			r.Post("/runs/{run_id}/subjects:batch", featureCtrl.BatchSubjects)
			r.Post("/runs/{run_id}/items:batch", featureCtrl.BatchItems)
			r.Patch("/runs/{run_id}", featureCtrl.UpdateRun)
			r.Patch("/runs/{run_id}/items/{version_id}", featureCtrl.UpdateItem)
			r.Post("/runs/{run_id}/values/numeric:batch", featureCtrl.WriteNumericValues)
			r.Post("/runs/{run_id}:complete", featureCtrl.CompleteRun)
			r.Post("/runs/{run_id}:fail", featureCtrl.FailRun)
			r.Post("/runs/{run_id}:cancel", featureCtrl.CancelRun)

			r.Get("/values/numeric", featureCtrl.QueryNumericValues)
			r.Get("/values/numeric/latest", featureCtrl.QueryLatestNumericValues)
			r.Get("/values/numeric/cross-section", featureCtrl.QueryNumericCrossSection)
			r.Post("/values/numeric:stats", featureCtrl.NumericValueStats)

			r.Post("/backfills", featureCtrl.CreateBackfill)
			r.Get("/backfills", featureCtrl.ListBackfills)
			r.Get("/backfills/{backfill_id}", featureCtrl.GetBackfill)
			r.Post("/backfills/{backfill_id}/runs:claim", featureCtrl.ClaimBackfillRun)
			r.Post("/backfills/{backfill_id}:retry-failed", featureCtrl.RetryFailedBackfill)
			r.Post("/backfills/{backfill_id}:cancel", featureCtrl.CancelBackfill)

			r.Post("/purges:preview", featureCtrl.PreviewPurge)
			r.Post("/purges", featureCtrl.SubmitPurge)
			r.Get("/purges", featureCtrl.ListPurges)
			r.Get("/purges/{purge_id}", featureCtrl.GetPurge)
			r.Post("/purges/{purge_id}:cancel", featureCtrl.CancelPurge)
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

		// ====== Atlas governed knowledge persistence ======
		kgCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_ATLAS_KG)
		if err != nil {
			return err
		}
		kgCtrl := kgCtrlComp.(*controller.AtlasKGController)

		r.Route("/api/v1/atlas-kg", func(r chi.Router) {
			r.Post("/extraction-runs", kgCtrl.CreateExtractionRun)
			r.Get("/extraction-runs", kgCtrl.ListExtractionRuns)
			r.Get("/extraction-runs:completed", kgCtrl.FindCompletedExtractionRun)
			r.Get("/extraction-runs:reusable", kgCtrl.FindReusableExtraction)
			r.Get("/extraction-runs/{run_id}", kgCtrl.GetExtractionRun)
			r.Put("/extraction-runs/{run_id}", kgCtrl.UpdateExtractionRun)
			r.Post("/extraction-runs/{run_id}/result", kgCtrl.SaveExtractionResult)
			r.Post("/governance/{kind}", kgCtrl.SaveGovernanceRecord)
			r.Get("/governance/{kind}", kgCtrl.ListGovernanceRecords)
			r.Post("/entities:batch", kgCtrl.UpsertEntities)
			r.Get("/entities", kgCtrl.ListEntities)
			r.Post("/entity-aliases:batch", kgCtrl.UpsertEntityAliases)
			r.Post("/security-entity-links:batch", kgCtrl.UpsertSecurityEntityLinks)
			r.Post("/claims:batch", kgCtrl.UpsertClaims)
			r.Get("/claims", kgCtrl.ListClaims)
		})

		// ====== Atlas controlled Neo4j projection/query (no arbitrary Cypher) ======
		graphCtrlComp, err := c.Resolve(bizConsts.COMP_CTRL_ATLAS_GRAPH)
		if err == nil {
			graphCtrl := graphCtrlComp.(*controller.AtlasGraphController)

			r.Route("/api/v1/atlas-graph", func(r chi.Router) {
				r.Post("/projection:batch", graphCtrl.ProjectBatch)
				r.Get("/search", graphCtrl.SearchNodes)
				r.Get("/stats", graphCtrl.GetGraphStats)
				r.Get("/entities/{entity_id}/neighborhood", graphCtrl.GetNeighborhood)
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
