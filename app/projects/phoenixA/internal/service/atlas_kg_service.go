package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type AtlasKGService struct {
	*core.BaseComponent
	Dao *dao.AtlasKGDao `infra:"dep:dao_atlas_kg"`
}

func NewAtlasKGService() *AtlasKGService {
	return &AtlasKGService{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_ATLAS_KG, consts.COMPONENT_LOGGING)}
}

func (s *AtlasKGService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_atlas_kg is nil")
	}
	return s.BaseComponent.Start(ctx)
}
func (s *AtlasKGService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *AtlasKGService) UpsertExtractionRun(ctx context.Context, run *model.AtlasExtractionRun) error {
	return s.Dao.UpsertExtractionRun(ctx, run)
}
func (s *AtlasKGService) SaveExtractionResult(ctx context.Context, id string, result []byte) error {
	return s.Dao.SaveExtractionResult(ctx, id, result)
}
func (s *AtlasKGService) GetExtractionRun(ctx context.Context, id string) (*model.AtlasExtractionRun, error) {
	return s.Dao.GetExtractionRun(ctx, id)
}
func (s *AtlasKGService) ListExtractionRuns(ctx context.Context, status string, limit int) ([]*model.AtlasExtractionRun, error) {
	return s.Dao.ListExtractionRuns(ctx, status, boundedAtlasLimit(limit))
}
func (s *AtlasKGService) FindCompletedExtractionRun(
	ctx context.Context,
	sourceDocumentID, semanticVersion, pipelineVersion string,
) (*model.AtlasExtractionRun, error) {
	return s.Dao.FindCompletedExtractionRun(
		ctx, sourceDocumentID, semanticVersion, pipelineVersion,
	)
}
func (s *AtlasKGService) FindReusableExtraction(
	ctx context.Context,
	sourceDocumentID, semanticVersion, pipelineVersion, promptSignature string,
) (*model.AtlasExtractionRun, error) {
	return s.Dao.FindReusableExtraction(
		ctx,
		sourceDocumentID,
		semanticVersion,
		pipelineVersion,
		promptSignature,
	)
}
func (s *AtlasKGService) SaveGovernance(ctx context.Context, record *model.AtlasGovernanceRecord) error {
	return s.Dao.SaveGovernance(ctx, record)
}
func (s *AtlasKGService) ListGovernance(ctx context.Context, kind string, limit int) ([]*model.AtlasGovernanceRecord, error) {
	return s.Dao.ListGovernance(ctx, kind, boundedAtlasLimit(limit))
}
func (s *AtlasKGService) UpsertEntities(ctx context.Context, entities []*model.AtlasKnowledgeEntity) error {
	return s.Dao.UpsertEntities(ctx, entities)
}
func (s *AtlasKGService) ListEntities(
	ctx context.Context,
	query, entityType string,
	exact bool,
	limit int,
) ([]*model.AtlasKnowledgeEntity, error) {
	return s.Dao.ListEntities(ctx, query, entityType, exact, boundedAtlasLimit(limit))
}
func (s *AtlasKGService) UpsertEntityAliases(
	ctx context.Context,
	aliases []*model.AtlasEntityAlias,
) error {
	return s.Dao.UpsertEntityAliases(ctx, aliases)
}
func (s *AtlasKGService) UpsertSecurityEntityLinks(
	ctx context.Context,
	links []*model.AtlasSecurityEntityLink,
) error {
	return s.Dao.UpsertSecurityEntityLinks(ctx, links)
}
func (s *AtlasKGService) UpsertClaims(ctx context.Context, claims []*model.AtlasClaim) error {
	return s.Dao.UpsertClaims(ctx, claims)
}
func (s *AtlasKGService) ListClaims(ctx context.Context, entityID, predicate string, limit int) ([]*model.AtlasClaim, error) {
	return s.Dao.ListClaims(ctx, entityID, predicate, boundedAtlasLimit(limit))
}

func boundedAtlasLimit(limit int) int {
	if limit <= 0 {
		return 100
	}
	if limit > 1000 {
		return 1000
	}
	return limit
}
