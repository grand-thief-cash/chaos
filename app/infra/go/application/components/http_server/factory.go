package http_server

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct {
	container *core.Container
}

func NewFactory(c *core.Container) *Factory { return &Factory{container: c} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	httpCfg, ok := cfg.(*HTTPServerConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for http_server component (need *HTTPServerConfig)")
	}
	if !httpCfg.Enabled {
		return nil, fmt.Errorf("http_server component disabled")
	}
	return NewHTTPServerComponent(httpCfg, f.container), nil
}
