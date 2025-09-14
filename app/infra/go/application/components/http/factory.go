package http

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct {
	container *core.Container
}

func NewFactory(c *core.Container) *Factory { return &Factory{container: c} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	httpCfg, ok := cfg.(*HTTPConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for http component (need *HTTPConfig)")
	}
	if !httpCfg.Enabled {
		return nil, fmt.Errorf("http component disabled")
	}
	return NewHTTPComponent(httpCfg, f.container), nil
}
