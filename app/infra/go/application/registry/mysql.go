package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_MYSQL, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.MySQL == nil || !cfg.MySQL.Enabled {
			return false, nil, nil
		}
		factory := mysql.NewFactory()
		comp, err := factory.Create(cfg.MySQL)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
