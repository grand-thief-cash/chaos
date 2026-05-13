package dao

import (
	"context"
	"fmt"

	neo4jcomp "github.com/grand-thief-cash/chaos/app/infra/go/application/components/neo4j"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
)

// GraphDao wraps the Neo4j infra component for graph operations.
type GraphDao struct {
	*core.BaseComponent
	Neo4j *neo4jcomp.Neo4jComponent `infra:"dep:neo4j"`
}

func NewGraphDao() *GraphDao {
	return &GraphDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_GRAPH),
	}
}

func (d *GraphDao) Start(ctx context.Context) error { return d.BaseComponent.Start(ctx) }
func (d *GraphDao) Stop(ctx context.Context) error  { return d.BaseComponent.Stop(ctx) }

// RunCypher executes a read-only Cypher query.
func (d *GraphDao) RunCypher(ctx context.Context, cypher string, params map[string]any) ([]map[string]any, error) {
	return d.Neo4j.RunCypher(ctx, cypher, params)
}

// RunCypherWrite executes a write Cypher query.
func (d *GraphDao) RunCypherWrite(ctx context.Context, cypher string, params map[string]any) (int64, error) {
	return d.Neo4j.RunCypherWrite(ctx, cypher, params)
}

// MergeNode creates or merges a node by label and merge key.
func (d *GraphDao) MergeNode(ctx context.Context, label, mergeKey, mergeValue string, props map[string]any) (int64, error) {
	cypher := fmt.Sprintf("MERGE (n:%s {%s: $merge_val}) SET n += $props", label, mergeKey)
	return d.Neo4j.RunCypherWrite(ctx, cypher, map[string]any{"merge_val": mergeValue, "props": props})
}

// MergeEdge creates or merges a relationship between two nodes.
func (d *GraphDao) MergeEdge(ctx context.Context, fromLabel, fromKey, fromVal, toLabel, toKey, toVal, relType string, attrs map[string]any) (int64, error) {
	cypher := fmt.Sprintf(
		"MATCH (a:%s {%s: $from_val}) MATCH (b:%s {%s: $to_val}) MERGE (a)-[r:%s]->(b) SET r += $attrs",
		fromLabel, fromKey, toLabel, toKey, relType,
	)
	params := map[string]any{
		"from_val": fromVal,
		"to_val":   toVal,
		"attrs":    attrs,
	}
	return d.Neo4j.RunCypherWrite(ctx, cypher, params)
}

// SearchNodes performs full-text search across all node names.
func (d *GraphDao) SearchNodes(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	if limit <= 0 {
		limit = 20
	}
	cypher := `
		CALL {
			MATCH (n) WHERE n.name CONTAINS $q RETURN n, labels(n)[0] AS label
			UNION
			MATCH (n:Company) WHERE n.normalized_name CONTAINS $q RETURN n, 'Company' AS label
		}
		RETURN DISTINCT properties(n) AS props, label
		LIMIT $limit
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"q": query, "limit": limit})
}

// GetCompanyFull returns a company and all its direct relationships.
func (d *GraphDao) GetCompanyFull(ctx context.Context, name string) ([]map[string]any, error) {
	cypher := `
		MATCH (c:Company {normalized_name: $name})
		OPTIONAL MATCH (c)-[r]-(n)
		RETURN c, collect(DISTINCT {rel_type: type(r), direction: CASE
			WHEN startNode(r) = c THEN 'outgoing' ELSE 'incoming' END,
			props: properties(r), neighbor: properties(n), neighbor_label: labels(n)[0]
		}) AS relationships
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"name": name})
}

// GetCompanyChain returns the supply chain around a company.
func (d *GraphDao) GetCompanyChain(ctx context.Context, name string, maxHops int) (map[string]any, error) {
	if maxHops <= 0 || maxHops > 5 {
		maxHops = 3
	}
	nodeCypher := fmt.Sprintf(`
		MATCH (c:Company {normalized_name: $name})
		CALL {
			WITH c
			MATCH path = (c)-[*1..%d]-(n)
			RETURN nodes(path) AS ns
			LIMIT 200
		}
		UNWIND ns AS node
		WITH DISTINCT node
		RETURN labels(node)[0] AS label, properties(node) AS props
	`, maxHops)
	nodes, err := d.Neo4j.RunCypher(ctx, nodeCypher, map[string]any{"name": name})
	if err != nil {
		return nil, err
	}
	edgeCypher := fmt.Sprintf(`
		MATCH (c:Company {normalized_name: $name})
		CALL {
			WITH c
			MATCH (c)-[r*1..%d]-(n)
			UNWIND r AS rel
			RETURN DISTINCT startNode(rel) AS s, endNode(rel) AS e, type(rel) AS rtype, properties(rel) AS rprops
			LIMIT 500
		}
		RETURN properties(s) AS source, properties(e) AS target, rtype, rprops
	`, maxHops)
	edges, err := d.Neo4j.RunCypher(ctx, edgeCypher, map[string]any{"name": name})
	if err != nil {
		return nil, err
	}
	return map[string]any{"nodes": nodes, "edges": edges}, nil
}

// GetCompanyTimeline returns time-ordered events for a company.
func (d *GraphDao) GetCompanyTimeline(ctx context.Context, name string) ([]map[string]any, error) {
	cypher := `
		MATCH (c:Company {normalized_name: $name})-[r]-(n)
		WHERE r.time IS NOT NULL AND r.time <> '' AND r.time <> 'unknown'
		RETURN type(r) AS rel_type, properties(r) AS rel_props,
			   labels(n)[0] AS neighbor_label, n.name AS neighbor_name, r.time AS time
		ORDER BY r.time DESC
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"name": name})
}

// GetCompetitors returns competitors of a company.
func (d *GraphDao) GetCompetitors(ctx context.Context, name string) ([]map[string]any, error) {
	cypher := `
		MATCH (c:Company {normalized_name: $name})-[r:COMPETITOR_OF]-(comp:Company)
		RETURN comp.normalized_name AS competitor, comp.ticker AS ticker,
			   r.product AS product, r.competition_type AS competition_type,
			   r.dimension AS dimension
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"name": name})
}

// GetEventImpacts returns companies impacted by an event.
func (d *GraphDao) GetEventImpacts(ctx context.Context, eventName string) ([]map[string]any, error) {
	cypher := `
		MATCH (e:Event {name: $name})-[r:IMPACT_ON]->(c:Company)
		RETURN c.normalized_name AS company, c.ticker AS ticker,
			   r.impact_direction AS direction, r.impact_type AS type,
			   r.impact_strength AS strength, r.transmission_path AS path
		ORDER BY r.impact_strength DESC
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"name": eventName})
}

// GetResourceRelatedCompanies returns companies related to a resource.
func (d *GraphDao) GetResourceRelatedCompanies(ctx context.Context, resourceName string) ([]map[string]any, error) {
	cypher := `
		MATCH (r:Resource {name: $name})<-[rel]-(c:Company)
		RETURN c.normalized_name AS name, c.ticker AS ticker,
			   type(rel) AS rel_type, rel.confidence AS confidence
	`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"name": resourceName})
}

// GetGraphStats returns overall graph statistics.
func (d *GraphDao) GetGraphStats(ctx context.Context) (map[string]any, error) {
	labels := []string{"Company", "Product", "Resource", "Industry", "Technology", "Event", "Policy", "Asset", "Market"}
	nodeCounts := make(map[string]any)
	totalNodes := 0
	for _, label := range labels {
		rows, err := d.Neo4j.RunCypher(ctx, fmt.Sprintf("MATCH (n:%s) RETURN count(n) AS cnt", label), nil)
		if err != nil {
			return nil, err
		}
		cnt := 0
		if len(rows) > 0 {
			if v, ok := rows[0]["cnt"].(int64); ok {
				cnt = int(v)
			}
		}
		nodeCounts[label] = cnt
		totalNodes += cnt
	}
	// Total edges
	rows, err := d.Neo4j.RunCypher(ctx, "MATCH ()-[r]->() RETURN count(r) AS cnt", nil)
	if err != nil {
		return nil, err
	}
	totalEdges := 0
	if len(rows) > 0 {
		if v, ok := rows[0]["cnt"].(int64); ok {
			totalEdges = int(v)
		}
	}
	return map[string]any{
		"node_counts": nodeCounts,
		"total_nodes": totalNodes,
		"total_edges": totalEdges,
	}, nil
}

// GetRelTypeCounts returns relationship type counts for the catalog.
func (d *GraphDao) GetRelTypeCounts(ctx context.Context) (map[string]int, error) {
	cypher := `
		MATCH ()-[r]->()
		RETURN type(r) AS rel_type, count(r) AS cnt
		ORDER BY cnt DESC
	`
	rows, err := d.Neo4j.RunCypher(ctx, cypher, nil)
	if err != nil {
		return nil, fmt.Errorf("get rel type counts: %w", err)
	}
	result := make(map[string]int, len(rows))
	for _, row := range rows {
		relType, _ := row["rel_type"].(string)
		if cnt, ok := row["cnt"].(int64); ok {
			result[relType] = int(cnt)
		}
	}
	return result, nil
}

// EnsureSchema creates Neo4j constraints and indexes.
func (d *GraphDao) EnsureSchema(ctx context.Context) error {
	constraints := []string{
		"CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.normalized_name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (r:Resource) REQUIRE r.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (t:Technology) REQUIRE t.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (m:Market) REQUIRE m.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (a:Asset) REQUIRE a.name IS UNIQUE",
	}
	indexes := []string{
		"CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.name)",
		"CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.ticker)",
		"CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.time)",
	}
	for _, stmt := range append(constraints, indexes...) {
		if _, err := d.Neo4j.RunCypherWrite(ctx, stmt, nil); err != nil {
			return fmt.Errorf("ensure schema failed on: %s: %w", stmt, err)
		}
	}
	return nil
}
