package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
)

type AtlasGraphService struct {
	*core.BaseComponent
	Dao *dao.AtlasGraphDao `infra:"dep:dao_atlas_graph"`
}

func NewAtlasGraphService() *AtlasGraphService {
	return &AtlasGraphService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_ATLAS_GRAPH, consts.COMPONENT_LOGGING)}
}
func (s *AtlasGraphService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_atlas_graph is nil")
	}
	return s.BaseComponent.Start(ctx)
}
func (s *AtlasGraphService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }
func (s *AtlasGraphService) ProjectBatch(ctx context.Context, entities, claims []map[string]any) error {
	return s.Dao.ProjectBatch(ctx, entities, claims)
}
func (s *AtlasGraphService) Search(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	return s.Dao.Search(ctx, query, boundedAtlasLimit(limit))
}
func (s *AtlasGraphService) Neighborhood(ctx context.Context, entityID string, limit int) ([]map[string]any, error) {
	return s.Dao.Neighborhood(ctx, entityID, boundedAtlasLimit(limit))
}
func (s *AtlasGraphService) Stats(ctx context.Context) (map[string]any, error) {
	return s.Dao.Stats(ctx)
}
