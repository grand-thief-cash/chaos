package registry

import (
	neo4jcomp "github.com/grand-thief-cash/chaos/app/infra/go/application/components/neo4j"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	Register(consts.COMPONENT_NEO4J, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		if cfg.Neo4j == nil || !cfg.Neo4j.Enabled {
			return false, nil, nil
		}
		factory := neo4jcomp.NewFactory()
		comp, err := factory.Create(cfg.Neo4j)
		if err != nil {
			return true, nil, err
		}
		return true, comp, nil
	})
}

