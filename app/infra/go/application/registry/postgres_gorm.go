package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_POSTGRES_GORM, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.PostgresGORM == nil || !cfg.PostgresGORM.Enabled {
			return false, nil, nil
		}
		factory := postgresgorm.NewFactory()
		comp, err := factory.Create(cfg.PostgresGORM)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
