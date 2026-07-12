package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

func init() {
	// v2 Services
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewSecurityService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewBarsService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewTaxonomyService(), nil
	})

	// Shared resolve cache (security_registry + taxonomy_category natural-key → id).
	// Depends only on DAOs; TaxonomyService resolves/validates against it, SecurityService
	// invalidates it on security_registry upsert/delete (refactor §8.bis-1).
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewResolveCache(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewFinancialStatementService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewCorporateActionService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewAdjustFactorService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewLongHuBangService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewEquityStructureService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewCatalogService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewFieldDictionaryService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewFieldCoverageService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewResearchReportService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, service.NewKgService(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Neo4j == nil || !cfg.Neo4j.Enabled {
			return false, nil, nil
		}
		return true, service.NewGraphService(), nil
	})
}
