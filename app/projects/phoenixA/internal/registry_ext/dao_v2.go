package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

func init() {
	// v2 DAOs
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewSecurityRegistryDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewBarsDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewTaxonomyDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewStrategyRunDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewFinancialStatementDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewCorporateActionDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewSchemaDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewKgDao("security"), nil
	})

	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Neo4j == nil || !cfg.Neo4j.Enabled {
			return false, nil, nil
		}
		return true, dao.NewGraphDao(), nil
	})
}
