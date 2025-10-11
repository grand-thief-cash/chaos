package registry

import (
	"fmt"

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
		if cfg.Telemetry.ServiceName == "" && cfg.APPInfo != nil {
			cfg.Telemetry.ServiceName = cfg.APPInfo.APPName
		}
		if cfg.Telemetry.ServiceName == "" {
			return false, nil, fmt.Errorf("telemetry.service_name empty and app_info.app_name not provided")
		}
		comp := telemetry.NewTelemetryComponent(cfg.Telemetry)
		return true, comp, nil
	})
}
