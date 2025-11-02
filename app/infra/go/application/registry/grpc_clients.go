package registry

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_GRPC_CLIENTS, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.GRPCClients == nil || !cfg.GRPCClients.Enabled {
			return false, nil, nil
		}
		factory := grpc_client.NewFactory()
		comp, err := factory.Create(cfg.GRPCClients)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}
