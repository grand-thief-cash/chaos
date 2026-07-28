package dao

import (
	"context"

	neo4jcomp "github.com/grand-thief-cash/chaos/app/infra/go/application/components/neo4j"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
)

type AtlasGraphDao struct {
	*core.BaseComponent
	Neo4j *neo4jcomp.Neo4jComponent `infra:"dep:neo4j"`
}

func NewAtlasGraphDao() *AtlasGraphDao {
	return &AtlasGraphDao{BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_ATLAS_GRAPH)}
}
func (d *AtlasGraphDao) Start(ctx context.Context) error { return d.BaseComponent.Start(ctx) }
func (d *AtlasGraphDao) Stop(ctx context.Context) error  { return d.BaseComponent.Stop(ctx) }

func (d *AtlasGraphDao) ProjectBatch(ctx context.Context, entities, claims []map[string]any) error {
	const nodeCypher = `
		UNWIND $entities AS item
		MERGE (entity:AtlasEntity {id: item.id})
		SET entity.canonical_name = item.canonical_name,
		    entity.normalized_name = item.normalized_name,
		    entity.entity_type = item.entity_type,
		    entity.country_code = item.country_code`
	if _, err := d.Neo4j.RunCypherWrite(ctx, nodeCypher, map[string]any{"entities": entities}); err != nil {
		return err
	}
	const claimCypher = `
		UNWIND $claims AS item
		MATCH (subject:AtlasEntity {id: item.subject_entity_id})
		MATCH (object:AtlasEntity {id: item.object_entity_id})
		MERGE (subject)-[claim:ATLAS_CLAIM {id: item.id}]->(object)
		SET claim.predicate = item.canonical_predicate,
		    claim.assertion_type = item.assertion_type,
		    claim.source_document_id = item.source_document_id,
		    claim.confidence = item.confidence`
	_, err := d.Neo4j.RunCypherWrite(ctx, claimCypher, map[string]any{"claims": claims})
	return err
}

func (d *AtlasGraphDao) Search(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	const cypher = `
		MATCH (entity:AtlasEntity)
		WHERE toLower(entity.canonical_name) CONTAINS toLower($query)
		   OR toLower(entity.normalized_name) CONTAINS toLower($query)
		RETURN properties(entity) AS entity
		ORDER BY entity.canonical_name
		LIMIT $limit`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"query": query, "limit": limit})
}

func (d *AtlasGraphDao) Neighborhood(ctx context.Context, entityID string, limit int) ([]map[string]any, error) {
	const cypher = `
		MATCH (entity:AtlasEntity {id: $entity_id})-[claim:ATLAS_CLAIM]-(neighbor:AtlasEntity)
		RETURN properties(entity) AS entity, properties(claim) AS claim,
		       properties(neighbor) AS neighbor,
		       CASE WHEN startNode(claim) = entity THEN 'OUTGOING' ELSE 'INCOMING' END AS direction
		LIMIT $limit`
	return d.Neo4j.RunCypher(ctx, cypher, map[string]any{"entity_id": entityID, "limit": limit})
}

func (d *AtlasGraphDao) Stats(ctx context.Context) (map[string]any, error) {
	const cypher = `
		MATCH (entity:AtlasEntity)
		WITH count(entity) AS entities
		OPTIONAL MATCH ()-[claim:ATLAS_CLAIM]->()
		RETURN entities, count(claim) AS claims`
	rows, err := d.Neo4j.RunCypher(ctx, cypher, nil)
	if err != nil || len(rows) == 0 {
		return map[string]any{"entities": 0, "claims": 0}, err
	}
	return rows[0], nil
}

func (d *AtlasGraphDao) GetGraphStats(ctx context.Context) (map[string]any, error) {
	stats, err := d.Stats(ctx)
	if err != nil {
		return nil, err
	}
	entityCount := numericAsInt(stats["entities"])
	claimCount := numericAsInt(stats["claims"])
	return map[string]any{
		"node_counts": map[string]any{"AtlasEntity": entityCount},
		"total_nodes": entityCount,
		"total_edges": claimCount,
	}, nil
}

func (d *AtlasGraphDao) GetRelTypeCounts(ctx context.Context) (map[string]int, error) {
	stats, err := d.Stats(ctx)
	if err != nil {
		return nil, err
	}
	return map[string]int{"ATLAS_CLAIM": numericAsInt(stats["claims"])}, nil
}

func numericAsInt(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	default:
		return 0
	}
}
