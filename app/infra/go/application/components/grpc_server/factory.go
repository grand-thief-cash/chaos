// go
// file: app/infra/go/application/components/grpc_server/factory.go
package grpc_server

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct {
	container *core.Container
}

func NewFactory(c *core.Container) *Factory { return &Factory{container: c} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	c, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for grpc_server component (*Config required)")
	}
	if c == nil || !c.Enabled {
		return nil, fmt.Errorf("grpc_server component disabled")
	}
	setDefaults(c)
	return NewGRPCServerComponent(c, f.container), nil
}

func setDefaults(c *Config) {
	if c.Address == "" {
		c.Address = ":50051"
	}
	if c.MaxRecvMsgSize == 0 {
		c.MaxRecvMsgSize = 4 << 20 // 4MB
	}
	if c.MaxSendMsgSize == 0 {
		c.MaxSendMsgSize = 4 << 20
	}
	if c.GracefulTimeout == 0 {
		c.GracefulTimeout = 10 * 1e9 // 10s
	}
}
