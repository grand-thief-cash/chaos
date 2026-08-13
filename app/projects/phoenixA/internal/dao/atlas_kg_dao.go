package dao

import (
	"context"
	"fmt"
	"time"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type AtlasKGDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewAtlasKGDao(dsName string) *AtlasKGDao {
	return &AtlasKGDao{BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_ATLAS_KG), dsName: dsName}
}

func (d *AtlasKGDao) Start(ctx context.Context) error {
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return fmt.Errorf("get gorm db %s failed: %w", d.dsName, err)
	}
	d.db = db
	return nil
}

func (d *AtlasKGDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

func (d *AtlasKGDao) UpsertExtractionRun(ctx context.Context, run *model.AtlasExtractionRun) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "id"}},
		DoUpdates: clause.AssignmentColumns([]string{"status", "payload", "updated_at"}),
	}).Create(run).Error
}

func (d *AtlasKGDao) SaveExtractionResult(ctx context.Context, id string, result []byte) error {
	tx := d.db.WithContext(ctx).Model(&model.AtlasExtractionRun{}).
		Where("id = ?", id).Updates(map[string]any{"result": result, "updated_at": gorm.Expr("NOW()")})
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *AtlasKGDao) GetExtractionRun(ctx context.Context, id string) (*model.AtlasExtractionRun, error) {
	var result model.AtlasExtractionRun
	if err := d.db.WithContext(ctx).First(&result, "id = ?", id).Error; err != nil {
		return nil, err
	}
	return &result, nil
}

func (d *AtlasKGDao) ListExtractionRuns(ctx context.Context, status string, limit int) ([]*model.AtlasExtractionRun, error) {
	var result []*model.AtlasExtractionRun
	q := d.db.WithContext(ctx).Order("updated_at DESC").Limit(limit)
	if status != "" {
		q = q.Where("status = ?", status)
	}
	return result, q.Find(&result).Error
}

func (d *AtlasKGDao) FindCompletedExtractionRun(
	ctx context.Context,
	sourceDocumentID, semanticVersion, pipelineVersion string,
) (*model.AtlasExtractionRun, error) {
	var result model.AtlasExtractionRun
	err := d.db.WithContext(ctx).
		Where("source_document_id = ? AND status = ?", sourceDocumentID, "SUCCEEDED").
		Where("payload ->> 'semantic_version' = ?", semanticVersion).
		Where("payload ->> 'pipeline_version' = ?", pipelineVersion).
		Order("updated_at DESC").
		First(&result).Error
	if err != nil {
		return nil, err
	}
	return &result, nil
}

func (d *AtlasKGDao) FindReusableExtraction(
	ctx context.Context,
	sourceDocumentID, semanticVersion, pipelineVersion, promptSignature string,
) (*model.AtlasExtractionRun, error) {
	var result model.AtlasExtractionRun
	err := d.db.WithContext(ctx).
		Where("source_document_id = ? AND result IS NOT NULL", sourceDocumentID).
		Where("payload ->> 'semantic_version' = ?", semanticVersion).
		Where("payload ->> 'pipeline_version' = ?", pipelineVersion).
		Where("payload ->> 'prompt_signature' = ?", promptSignature).
		Order("updated_at DESC").
		First(&result).Error
	if err != nil {
		return nil, err
	}
	return &result, nil
}

func (d *AtlasKGDao) SaveGovernance(ctx context.Context, record *model.AtlasGovernanceRecord) error {
	db := d.db.WithContext(ctx)
	if record.Version != "" {
		return db.Where("kind = ? AND version = ?", record.Kind, record.Version).
			Assign(map[string]any{
				"status": record.Status, "payload": record.Payload, "updated_at": gorm.Expr("NOW()"),
			}).
			FirstOrCreate(record).Error
	}
	return db.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "id"}},
		DoUpdates: clause.AssignmentColumns([]string{"status", "payload", "updated_at"}),
	}).Create(record).Error
}

func (d *AtlasKGDao) ListGovernance(ctx context.Context, kind string, limit int) ([]*model.AtlasGovernanceRecord, error) {
	var result []*model.AtlasGovernanceRecord
	err := d.db.WithContext(ctx).Where("kind = ?", kind).
		Order("created_at DESC").Limit(limit).Find(&result).Error
	return result, err
}

func (d *AtlasKGDao) UpsertEntities(ctx context.Context, entities []*model.AtlasKnowledgeEntity) error {
	if len(entities) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "id"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"canonical_name", "normalized_name", "entity_type", "country_code",
			"resolution_state", "attributes", "updated_at",
		}),
	}).CreateInBatches(entities, 200).Error
}

func (d *AtlasKGDao) ListEntities(
	ctx context.Context,
	query, entityType string,
	exact bool,
	limit int,
) ([]*model.AtlasKnowledgeEntity, error) {
	var result []*model.AtlasKnowledgeEntity
	q := d.db.WithContext(ctx).Order("updated_at DESC").Limit(limit)
	if query != "" {
		if exact {
			q = q.Where(
				`normalized_name = ? OR EXISTS (
					SELECT 1 FROM atlas_kg.entity_alias aliases
					WHERE aliases.entity_id = atlas_kg.knowledge_entity.id
					  AND aliases.normalized_alias = ?
				)`,
				query,
				query,
			)
		} else {
			pattern := "%" + query + "%"
			q = q.Where(
				`normalized_name ILIKE ? OR EXISTS (
					SELECT 1 FROM atlas_kg.entity_alias aliases
					WHERE aliases.entity_id = atlas_kg.knowledge_entity.id
					  AND aliases.normalized_alias ILIKE ?
				)`,
				pattern,
				pattern,
			)
		}
	}
	if entityType != "" {
		q = q.Where("entity_type = ?", entityType)
	}
	return result, q.Find(&result).Error
}

func (d *AtlasKGDao) UpsertEntityAliases(
	ctx context.Context,
	aliases []*model.AtlasEntityAlias,
) error {
	if len(aliases) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "entity_id"}, {Name: "normalized_alias"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"alias", "language", "source",
		}),
	}).CreateInBatches(aliases, 200).Error
}

func (d *AtlasKGDao) UpsertSecurityEntityLinks(
	ctx context.Context,
	links []*model.AtlasSecurityEntityLink,
) error {
	if len(links) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "entity_id"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"security_id", "confidence", "resolution_method",
		}),
	}).CreateInBatches(links, 200).Error
}

func (d *AtlasKGDao) UpsertClaims(ctx context.Context, claims []*model.AtlasClaim) error {
	if len(claims) == 0 {
		return nil
	}
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "id"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"subject_entity_id", "object_entity_id", "canonical_predicate",
			"assertion_type", "status", "payload", "updated_at",
		}),
	}).CreateInBatches(claims, 200).Error
}

func (d *AtlasKGDao) ListClaims(ctx context.Context, entityID, predicate string, limit int) ([]*model.AtlasClaim, error) {
	var result []*model.AtlasClaim
	q := d.db.WithContext(ctx).Order("updated_at DESC").Limit(limit)
	if entityID != "" {
		q = q.Where("subject_entity_id = ? OR object_entity_id = ?", entityID, entityID)
	}
	if predicate != "" {
		q = q.Where("canonical_predicate = ?", predicate)
	}
	return result, q.Find(&result).Error
}

// ---------------- Sample Run ----------------

func (d *AtlasKGDao) CreateSampleRun(ctx context.Context, run *model.AtlasSampleRun) error {
	return d.db.WithContext(ctx).Create(run).Error
}

func (d *AtlasKGDao) GetSampleRun(ctx context.Context, id string) (*model.AtlasSampleRun, error) {
	var result model.AtlasSampleRun
	if err := d.db.WithContext(ctx).First(&result, "id = ?", id).Error; err != nil {
		return nil, err
	}
	return &result, nil
}

func (d *AtlasKGDao) ListSampleRuns(ctx context.Context, status string, limit int) ([]*model.AtlasSampleRun, error) {
	var result []*model.AtlasSampleRun
	q := d.db.WithContext(ctx).Order("updated_at DESC").Limit(limit)
	if status != "" {
		q = q.Where("status = ?", status)
	}
	return result, q.Find(&result).Error
}

func (d *AtlasKGDao) UpdateSampleRunStatus(
	ctx context.Context,
	id, status string,
	startedAt, completedAt *time.Time,
	errorCode, errorMessage *string,
) error {
	updates := map[string]any{"status": status, "updated_at": gorm.Expr("NOW()")}
	if startedAt != nil {
		updates["started_at"] = *startedAt
	}
	if completedAt != nil {
		updates["completed_at"] = *completedAt
	}
	if errorCode != nil {
		updates["error_code"] = *errorCode
	}
	if errorMessage != nil {
		updates["error_message"] = *errorMessage
	}
	tx := d.db.WithContext(ctx).Model(&model.AtlasSampleRun{}).
		Where("id = ?", id).Updates(updates)
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *AtlasKGDao) UpdateSampleRunProgress(
	ctx context.Context,
	id string,
	current, total int,
	progressMessage *string,
) error {
	updates := map[string]any{
		"current":    current,
		"total":      total,
		"updated_at": gorm.Expr("NOW()"),
	}
	if progressMessage != nil {
		updates["progress_message"] = *progressMessage
	}
	tx := d.db.WithContext(ctx).Model(&model.AtlasSampleRun{}).
		Where("id = ?", id).Updates(updates)
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *AtlasKGDao) UpdateSampleRunSampledDocs(
	ctx context.Context,
	id string,
	sampledDocumentIDs model.StringArray,
) error {
	tx := d.db.WithContext(ctx).Model(&model.AtlasSampleRun{}).
		Where("id = ?", id).
		Updates(map[string]any{
			"sampled_document_ids": sampledDocumentIDs,
			"updated_at":           gorm.Expr("NOW()"),
		})
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

// ---------------- Sample Category Result ----------------

func (d *AtlasKGDao) UpsertSampleCategoryResult(
	ctx context.Context,
	result *model.AtlasSampleCategoryResult,
) error {
	return d.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "sample_run_id"}, {Name: "report_type"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"document_count", "raw_results", "generated_at", "updated_at",
		}),
	}).Create(result).Error
}

func (d *AtlasKGDao) UpdateSampleFieldSummary(
	ctx context.Context,
	sampleRunID, reportType string,
	fieldSummary []byte,
) error {
	tx := d.db.WithContext(ctx).Model(&model.AtlasSampleCategoryResult{}).
		Where("sample_run_id = ? AND report_type = ?", sampleRunID, reportType).
		Updates(map[string]any{
			"field_summary": fieldSummary,
			"updated_at":    gorm.Expr("NOW()"),
		})
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *AtlasKGDao) GetSampleCategoryResult(
	ctx context.Context,
	sampleRunID, reportType string,
) (*model.AtlasSampleCategoryResult, error) {
	var result model.AtlasSampleCategoryResult
	err := d.db.WithContext(ctx).
		Where("sample_run_id = ? AND report_type = ?", sampleRunID, reportType).
		First(&result).Error
	if err != nil {
		return nil, err
	}
	return &result, nil
}

func (d *AtlasKGDao) ListSampleCategoryResults(
	ctx context.Context,
	sampleRunID string,
) ([]*model.AtlasSampleCategoryResult, error) {
	var result []*model.AtlasSampleCategoryResult
	err := d.db.WithContext(ctx).
		Where("sample_run_id = ?", sampleRunID).
		Order("report_type ASC").Find(&result).Error
	return result, err
}

// ---------------- Sample Document Result ----------------

func (d *AtlasKGDao) CreateSampleDocumentResult(
	ctx context.Context,
	doc *model.AtlasSampleDocumentResult,
) error {
	return d.db.WithContext(ctx).Create(doc).Error
}

func (d *AtlasKGDao) UpdateSampleDocumentResult(
	ctx context.Context,
	id, status string,
	startedAt, completedAt *time.Time,
	durationMs *int,
	errorCode, errorMessage *string,
) error {
	updates := map[string]any{"status": status, "updated_at": gorm.Expr("NOW()")}
	if startedAt != nil {
		updates["started_at"] = *startedAt
	}
	if completedAt != nil {
		updates["completed_at"] = *completedAt
	}
	if durationMs != nil {
		updates["duration_ms"] = *durationMs
	}
	if errorCode != nil {
		updates["error_code"] = *errorCode
	}
	if errorMessage != nil {
		updates["error_message"] = *errorMessage
	}
	tx := d.db.WithContext(ctx).Model(&model.AtlasSampleDocumentResult{}).
		Where("id = ?", id).Updates(updates)
	if tx.Error != nil {
		return tx.Error
	}
	if tx.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return nil
}

func (d *AtlasKGDao) ListSampleDocumentResults(
	ctx context.Context,
	sampleRunID string,
) ([]*model.AtlasSampleDocumentResult, error) {
	var result []*model.AtlasSampleDocumentResult
	err := d.db.WithContext(ctx).
		Where("sample_run_id = ?", sampleRunID).
		Order("report_type ASC, created_at ASC").Find(&result).Error
	return result, err
}
