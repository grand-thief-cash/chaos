package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_MYSQL_GORM, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.MySQLGORM == nil || !cfg.MySQLGORM.Enabled {
			return false, nil, nil
		}
		factory := mysqlgorm.NewFactory()
		comp, err := factory.Create(cfg.MySQLGORM)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
