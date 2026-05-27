package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/controller"
)

func init() {
	// v2 Controllers
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewSecurityController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewBarsController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewTaxonomyController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewStrategyRunController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewFinancialStatementController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewCorporateActionController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewAdjustFactorController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewLongHuBangController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewSchemaController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewCatalogController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, controller.NewKgController(), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Neo4j == nil || !cfg.Neo4j.Enabled {
			return false, nil, nil
		}
		return true, controller.NewGraphController(), nil
	})
}
