package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_LOGGING, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Logging == nil || !cfg.Logging.Enabled {
			return false, nil, nil
		}
		factory := logging.NewFactory()
		comp, err := factory.Create(cfg.Logging)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
