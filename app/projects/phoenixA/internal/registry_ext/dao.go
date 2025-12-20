package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

func init() {
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		// datasource name comes from phoenixA/config/config.yaml -> mysql_gorm.data_sources
		return true, dao.NewStockZhAListDao("security"), nil
	})
}
