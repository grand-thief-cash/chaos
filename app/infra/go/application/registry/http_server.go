package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_HTTP_SERVER, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.HTTPServer == nil || !cfg.HTTPServer.Enabled {
			return false, nil, nil
		}
		factory := http_server.NewFactory(c)
		comp, err := factory.Create(cfg.HTTPServer)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
