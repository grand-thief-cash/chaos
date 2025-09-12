// app/infra/go/application/components/grpc_client/factory.go
package grpc_client

import (
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct {
	logger logging.Logger
}

func NewFactory(logger logging.Logger) *Factory {
	return &Factory{logger: logger}
}

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	grpcConfig, ok := cfg.(*GRPCClientsConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for GRPC clients component, expected *GRPCClientsConfig")
	}
	if !grpcConfig.Enabled {
		return nil, fmt.Errorf("GRPC clients component is disabled")
	}
	f.setDefaults(grpcConfig)
	return NewGRPCClientComponent(grpcConfig, f.logger), nil
}

func (f *Factory) setDefaults(cfg *GRPCClientsConfig) {
	if cfg.DefaultTimeout == 0 {
		cfg.DefaultTimeout = 30 * time.Second
	}
	if cfg.HealthCheckInterval == 0 {
		cfg.HealthCheckInterval = 60 * time.Second
	}
	for name, clientConfig := range cfg.Clients {
		if clientConfig.Name == "" {
			clientConfig.Name = name
		}
		if clientConfig.MaxReceiveMessageLength == 0 {
			clientConfig.MaxReceiveMessageLength = 4 * 1024 * 1024
		}
		if clientConfig.MaxSendMessageLength == 0 {
			clientConfig.MaxSendMessageLength = 4 * 1024 * 1024
		}
		if clientConfig.Timeout == 0 {
			clientConfig.Timeout = cfg.DefaultTimeout
		}
	}
}
