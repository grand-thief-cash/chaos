package neo4j

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// Factory creates Neo4jComponent from config.
type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

// Create expects *neo4j.Config.
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	c, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for neo4j component (need *neo4j.Config)")
	}
	if c == nil || !c.Enabled {
		return nil, fmt.Errorf("neo4j component disabled")
	}
	return NewNeo4jComponent(c), nil
}

