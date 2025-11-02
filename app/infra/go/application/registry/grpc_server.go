package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_GRPC_SERVER, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.GRPCServer == nil || !cfg.GRPCServer.Enabled {
			return false, nil, nil
		}
		factory := grpc_server.NewFactory(c)
		comp, err := factory.Create(cfg.GRPCServer)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
