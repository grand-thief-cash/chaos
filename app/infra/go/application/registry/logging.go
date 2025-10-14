package registry

import (
	"strings"

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

		// Reuse APPInfo.APPName to fill filename when output is file and filename omitted
		if strings.EqualFold(cfg.Logging.Output, "file") {
			if cfg.Logging.FileConfig == nil {
				cfg.Logging.FileConfig = &logging.FileConfig{Dir: "./logs"}
			}
			if cfg.Logging.FileConfig.Filename == "" && cfg.APPInfo != nil && cfg.APPInfo.APPName != "" {
				cfg.Logging.FileConfig.Filename = cfg.APPInfo.APPName
			}
		}

		factory := logging.NewFactory()
		comp, err := factory.Create(cfg.Logging)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
