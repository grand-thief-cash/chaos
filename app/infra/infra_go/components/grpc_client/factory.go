// components/grpc_client/factory.go
package grpc_client

import (
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/infra_go/core"
)

// Factory GRPC客户端组件工厂
type Factory struct{}

// NewFactory 创建GRPC客户端组件工厂
func NewFactory() *Factory {
	return &Factory{}
}

// Create 创建GRPC客户端组件实例
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	grpcConfig, ok := cfg.(*GRPCClientsConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for GRPC clients component, expected *GRPCClientsConfig")
	}

	if !grpcConfig.Enabled {
		return nil, fmt.Errorf("GRPC clients component is disabled")
	}

	// 设置默认值
	f.setDefaults(grpcConfig)

	return NewGRPCClientComponent(grpcConfig), nil
}

// setDefaults 设置默认配置值
func (f *Factory) setDefaults(cfg *GRPCClientsConfig) {
	if cfg.DefaultTimeout == 0 {
		cfg.DefaultTimeout = 30 * time.Second
	}
	if cfg.HealthCheckInterval == 0 {
		cfg.HealthCheckInterval = 60 * time.Second
	}

	// 为每个客户端设置默认值
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