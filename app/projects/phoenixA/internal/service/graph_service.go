package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

// GraphService handles business logic for Neo4j graph operations.
type GraphService struct {
	*core.BaseComponent
	Dao *dao.GraphDao `infra:"dep:dao_graph"`
}

func NewGraphService() *GraphService {
	return &GraphService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_GRAPH, consts.COMPONENT_LOGGING),
	}
}

func (s *GraphService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_graph is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *GraphService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *GraphService) RunCypher(ctx context.Context, cypher string, params map[string]any) ([]map[string]any, error) {
	return s.Dao.RunCypher(ctx, cypher, params)
}

func (s *GraphService) RunCypherWrite(ctx context.Context, cypher string, params map[string]any) (int64, error) {
	return s.Dao.RunCypherWrite(ctx, cypher, params)
}

func (s *GraphService) MergeNode(ctx context.Context, label, mergeKey, mergeValue string, props map[string]any) (int64, error) {
	logging.Infof(ctx, "GraphService MergeNode %s {%s: %s}", label, mergeKey, mergeValue)
	return s.Dao.MergeNode(ctx, label, mergeKey, mergeValue, props)
}

func (s *GraphService) MergeEdge(ctx context.Context, fromLabel, fromKey, fromVal, toLabel, toKey, toVal, relType string, attrs map[string]any) (int64, error) {
	return s.Dao.MergeEdge(ctx, fromLabel, fromKey, fromVal, toLabel, toKey, toVal, relType, attrs)
}

func (s *GraphService) SearchNodes(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	return s.Dao.SearchNodes(ctx, query, limit)
}

func (s *GraphService) GetCompanyFull(ctx context.Context, name string) ([]map[string]any, error) {
	return s.Dao.GetCompanyFull(ctx, name)
}

func (s *GraphService) GetCompanyChain(ctx context.Context, name string, maxHops int) (map[string]any, error) {
	return s.Dao.GetCompanyChain(ctx, name, maxHops)
}

func (s *GraphService) GetCompanyTimeline(ctx context.Context, name string) ([]map[string]any, error) {
	return s.Dao.GetCompanyTimeline(ctx, name)
}

func (s *GraphService) GetCompetitors(ctx context.Context, name string) ([]map[string]any, error) {
	return s.Dao.GetCompetitors(ctx, name)
}

func (s *GraphService) GetEventImpacts(ctx context.Context, eventName string) ([]map[string]any, error) {
	return s.Dao.GetEventImpacts(ctx, eventName)
}

func (s *GraphService) GetResourceRelatedCompanies(ctx context.Context, resourceName string) ([]map[string]any, error) {
	return s.Dao.GetResourceRelatedCompanies(ctx, resourceName)
}

func (s *GraphService) GetGraphStats(ctx context.Context) (map[string]any, error) {
	return s.Dao.GetGraphStats(ctx)
}

func (s *GraphService) EnsureSchema(ctx context.Context) error {
	logging.Infof(ctx, "GraphService EnsureSchema")
	return s.Dao.EnsureSchema(ctx)
}

