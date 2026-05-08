package neo4j

import (
	"context"
	"fmt"

	n4j "github.com/neo4j/neo4j-go-driver/v5/neo4j"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// Neo4jComponent manages a Neo4j driver and provides Cypher execution helpers.
type Neo4jComponent struct {
	*core.BaseComponent
	cfg    *Config
	driver n4j.DriverWithContext
}

func NewNeo4jComponent(cfg *Config) *Neo4jComponent {
	setDefaults(cfg)
	return &Neo4jComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_NEO4J, consts.COMPONENT_LOGGING),
		cfg:           cfg,
	}
}

// Start creates the Neo4j driver and verifies connectivity.
func (c *Neo4jComponent) Start(ctx context.Context) error {
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if c.cfg == nil || !c.cfg.Enabled {
		return fmt.Errorf("neo4j component disabled or nil config")
	}

	auth := n4j.BasicAuth(c.cfg.Username, c.cfg.Password, "")
	driver, err := n4j.NewDriverWithContext(c.cfg.URI, auth, func(conf *n4j.Config) {
		conf.MaxConnectionPoolSize = c.cfg.MaxConnectionPoolSize
		if c.cfg.Encrypted {
			// Enable TLS without verification for simplicity; production should use custom TLS config.
		}
	})
	if err != nil {
		return fmt.Errorf("neo4j driver creation failed: %w", err)
	}

	if err := driver.VerifyConnectivity(ctx); err != nil {
		_ = driver.Close(ctx)
		return fmt.Errorf("neo4j connectivity check failed: %w", err)
	}

	c.driver = driver
	logging.Infof(ctx, "[neo4j] connected to %s database=%s pool=%d", c.cfg.URI, c.cfg.Database, c.cfg.MaxConnectionPoolSize)
	return nil
}

// Stop closes the driver.
func (c *Neo4jComponent) Stop(ctx context.Context) error {
	defer func() { _ = c.BaseComponent.Stop(ctx) }()
	if c.driver != nil {
		if err := c.driver.Close(ctx); err != nil {
			logging.Warnf(ctx, "[neo4j] close error: %v", err)
		} else {
			logging.Infof(ctx, "[neo4j] driver closed")
		}
	}
	return nil
}

// HealthCheck verifies the driver is still connected.
func (c *Neo4jComponent) HealthCheck() error {
	if err := c.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if c.driver == nil {
		return fmt.Errorf("neo4j driver not initialized")
	}
	ctx := context.Background()
	if err := c.driver.VerifyConnectivity(ctx); err != nil {
		return fmt.Errorf("neo4j health check failed: %w", err)
	}
	return nil
}

// Driver returns the underlying DriverWithContext.
func (c *Neo4jComponent) Driver() n4j.DriverWithContext {
	return c.driver
}

// Database returns the configured database name.
func (c *Neo4jComponent) Database() string {
	return c.cfg.Database
}

// RunCypher executes a read-only Cypher query and returns results as []map[string]any.
func (c *Neo4jComponent) RunCypher(ctx context.Context, cypher string, params map[string]any) ([]map[string]any, error) {
	session := c.driver.NewSession(ctx, n4j.SessionConfig{
		DatabaseName: c.cfg.Database,
		AccessMode:   n4j.AccessModeRead,
	})
	defer func() { _ = session.Close(ctx) }()

	result, err := session.Run(ctx, cypher, params)
	if err != nil {
		return nil, fmt.Errorf("neo4j read query failed: %w", err)
	}
	var rows []map[string]any
	for result.Next(ctx) {
		record := result.Record()
		row := make(map[string]any, len(record.Keys))
		for i, key := range record.Keys {
			row[key] = toSerializable(record.Values[i])
		}
		rows = append(rows, row)
	}
	if err := result.Err(); err != nil {
		return nil, fmt.Errorf("neo4j result iteration error: %w", err)
	}
	return rows, nil
}

// RunCypherWrite executes a write Cypher query inside an explicit write transaction.
func (c *Neo4jComponent) RunCypherWrite(ctx context.Context, cypher string, params map[string]any) (int64, error) {
	session := c.driver.NewSession(ctx, n4j.SessionConfig{
		DatabaseName: c.cfg.Database,
		AccessMode:   n4j.AccessModeWrite,
	})
	defer func() { _ = session.Close(ctx) }()

	summary, err := n4j.ExecuteQuery(ctx, c.driver, cypher, params,
		n4j.EagerResultTransformer,
		n4j.ExecuteQueryWithDatabase(c.cfg.Database),
	)
	if err != nil {
		return 0, fmt.Errorf("neo4j write query failed: %w", err)
	}
	counters := summary.Summary.Counters()
	affected := int64(counters.NodesCreated()) + int64(counters.RelationshipsCreated()) +
		int64(counters.PropertiesSet()) + int64(counters.NodesDeleted()) + int64(counters.RelationshipsDeleted())
	return affected, nil
}

// toSerializable recursively converts Neo4j-specific types (Node, Relationship, Path)
// into plain Go maps/slices that are JSON-serializable.
func toSerializable(v any) any {
	if v == nil {
		return nil
	}
	switch val := v.(type) {
	case n4j.Node:
		m := make(map[string]any, len(val.Props)+2)
		m["_labels"] = val.Labels
		m["_id"] = val.ElementId
		for k, pv := range val.Props {
			m[k] = toSerializable(pv)
		}
		return m
	case n4j.Relationship:
		m := map[string]any{
			"_type":     val.Type,
			"_id":       val.ElementId,
			"_startId":  val.StartElementId,
			"_endId":    val.EndElementId,
		}
		for k, pv := range val.Props {
			m[k] = toSerializable(pv)
		}
		return m
	case n4j.Path:
		nodes := make([]any, 0, len(val.Nodes))
		for _, nd := range val.Nodes {
			nodes = append(nodes, toSerializable(nd))
		}
		rels := make([]any, 0, len(val.Relationships))
		for _, r := range val.Relationships {
			rels = append(rels, toSerializable(r))
		}
		return map[string]any{"nodes": nodes, "relationships": rels}
	case []any:
		out := make([]any, len(val))
		for i, item := range val {
			out[i] = toSerializable(item)
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(val))
		for k, item := range val {
			out[k] = toSerializable(item)
		}
		return out
	default:
		return v // primitive types: string, int64, float64, bool, etc.
	}
}

