package http_client

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	c, ok := cfg.(*HTTPClientsConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for http_clients component")
	}
	if !c.Enabled {
		return nil, fmt.Errorf("http_clients component disabled")
	}
	return NewHTTPClientsComponent(c), nil
}
