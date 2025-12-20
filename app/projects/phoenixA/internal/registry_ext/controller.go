package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/api"
)

func init() {
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, api.NewStockZhAListController(), nil
	})
}
