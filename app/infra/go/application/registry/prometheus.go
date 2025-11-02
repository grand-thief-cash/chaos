package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/prometheus"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_PROMETHEUS, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Prometheus == nil || !cfg.Prometheus.Enabled {
			return false, nil, nil
		}
		factory := prometheus.NewFactory()
		comp, err := factory.Create(cfg.Prometheus)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
