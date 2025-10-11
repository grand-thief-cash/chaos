package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/telemetry"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_TELEMETRY, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Telemetry == nil || !cfg.Telemetry.Enabled {
			return false, nil, nil
		}
		comp := telemetry.NewTelemetryComponent(cfg.Telemetry)
		return true, comp, nil
	})
}
