package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_HTTP_CLIENTS, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.HTTPClient == nil || !cfg.HTTPClient.Enabled {
			return false, nil, nil
		}
		factory := http_client.NewFactory()
		comp, err := factory.Create(cfg.HTTPClient)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
