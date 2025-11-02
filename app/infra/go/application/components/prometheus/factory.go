package prometheus

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	c, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for prometheus component (*Config required)")
	}
	if c == nil || !c.Enabled {
		return nil, fmt.Errorf("prometheus component disabled")
	}
	if c.Address == "" {
		c.Address = ":9090"
	}
	if c.Path == "" {
		c.Path = "/metrics"
	}
	if c.CollectGoMetrics == false {
		c.CollectGoMetrics = true
	}
	if c.CollectProcess == false {
		c.CollectProcess = true
	}
	return NewComponent(c), nil
}
