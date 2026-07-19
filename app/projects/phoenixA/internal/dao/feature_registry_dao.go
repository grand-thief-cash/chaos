package dao

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
)

type FeatureRegistryDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewFeatureRegistryDao(dsName string) *FeatureRegistryDao {
	return &FeatureRegistryDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_FEATURE_REGISTRY),
		dsName:        dsName,
	}
}

func (d *FeatureRegistryDao) Start(ctx context.Context) error {
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

func (d *FeatureRegistryDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// SyncManifest writes one manifest atomically. Versions are always assembled
// as drafts first so database immutability guards never observe a partially
// published version; the final publish transition happens after dependency
// resolution and full-graph cycle validation.
func (d *FeatureRegistryDao) SyncManifest(ctx context.Context, manifest model.FeatureManifest, snapshot model.JSONValue) (string, error) {
	action := ""
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", "feature_registry:"+manifest.Feature.Code).Error; err != nil {
			return err
		}
		var definition model.FeatureDefinition
		err := tx.Where("feature_code = ?", manifest.Feature.Code).First(&definition).Error
		newDefinition := errors.Is(err, gorm.ErrRecordNotFound)
		if err != nil && !newDefinition {
			return err
		}

		tags := model.NewJSONValue(manifest.Feature.Tags)
		if newDefinition {
			definition = model.FeatureDefinition{
				FeatureCode: manifest.Feature.Code,
				DisplayName: manifest.Feature.DisplayName,
				Description: manifest.Feature.Description,
				Kind:        manifest.Feature.Kind,
				EntityType:  manifest.Feature.EntityType,
				ValueType:   manifest.Feature.ValueType,
				Unit:        manifest.Feature.Unit,
				Category:    manifest.Feature.Category,
				Owner:       manifest.Feature.Owner,
				Status:      "draft",
				Tags:        tags,
			}
			if err := tx.Create(&definition).Error; err != nil {
				return err
			}
		} else {
			if definition.Kind != manifest.Feature.Kind || definition.EntityType != manifest.Feature.EntityType || definition.ValueType != manifest.Feature.ValueType {
				return model.NewFeatureError(model.FeatureErrorConflict, "FEATURE_DEFINITION_IDENTITY_CONFLICT",
					"feature %s identity differs from the registered kind/entity_type/value_type", manifest.Feature.Code)
			}
			if err := tx.Model(&definition).Updates(map[string]any{
				"display_name": manifest.Feature.DisplayName,
				"description":  manifest.Feature.Description,
				"unit":         manifest.Feature.Unit,
				"category":     manifest.Feature.Category,
				"owner":        manifest.Feature.Owner,
				"tags":         tags,
				"updated_at":   gorm.Expr("NOW()"),
			}).Error; err != nil {
				return err
			}
		}

		var version model.FeatureVersion
		err = tx.Where("feature_id = ? AND version_number = ?", definition.ID, manifest.Version.Number).First(&version).Error
		newVersion := errors.Is(err, gorm.ErrRecordNotFound)
		if err != nil && !newVersion {
			return err
		}

		if newVersion {
			var maxVersion int
			if err := tx.Model(&model.FeatureVersion{}).
				Where("feature_id = ?", definition.ID).
				Select("COALESCE(MAX(version_number), 0)").Scan(&maxVersion).Error; err != nil {
				return err
			}
			if manifest.Version.Number <= maxVersion {
				return model.NewFeatureError(model.FeatureErrorConflict, "FEATURE_VERSION_NOT_MONOTONIC",
					"feature %s version %d must be greater than existing maximum %d", manifest.Feature.Code, manifest.Version.Number, maxVersion)
			}
			version = model.FeatureVersion{
				FeatureID:        definition.ID,
				VersionNumber:    manifest.Version.Number,
				Status:           "draft",
				Frequency:        manifest.Version.Frequency,
				AsOfSemantics:    manifest.Version.AsOfSemantics,
				MissingPolicy:    manifest.Version.MissingPolicy,
				ManifestChecksum: manifest.Version.ManifestChecksum,
				ManifestSnapshot: snapshot,
			}
			if err := tx.Create(&version).Error; err != nil {
				return err
			}
			action = "created"
		} else {
			if version.ManifestChecksum == manifest.Version.ManifestChecksum {
				action = "unchanged"
				if manifest.Version.Status == "published" && version.Status == "draft" {
					if err := d.publishVersionTx(tx, definition.ID, &version); err != nil {
						return err
					}
					action = "updated_draft"
				}
				return nil
			}
			if version.Status != "draft" {
				return model.NewFeatureError(model.FeatureErrorConflict, "MANIFEST_CHECKSUM_CONFLICT",
					"published feature %s@%d has checksum %s, received %s",
					manifest.Feature.Code, manifest.Version.Number, version.ManifestChecksum, manifest.Version.ManifestChecksum)
			}
			if err := tx.Model(&version).Updates(map[string]any{
				"frequency":         manifest.Version.Frequency,
				"as_of_semantics":   manifest.Version.AsOfSemantics,
				"missing_policy":    manifest.Version.MissingPolicy,
				"manifest_checksum": manifest.Version.ManifestChecksum,
				"manifest_snapshot": snapshot,
				"updated_at":        gorm.Expr("NOW()"),
			}).Error; err != nil {
				return err
			}
			if err := tx.Where("feature_version_id = ?", version.ID).Delete(&model.FeatureDependency{}).Error; err != nil {
				return err
			}
			if err := tx.Where("feature_version_id = ?", version.ID).Delete(&model.FeatureImplementation{}).Error; err != nil {
				return err
			}
			action = "updated_draft"
		}

		implementation := model.FeatureImplementation{
			FeatureVersionID:       version.ID,
			Kind:                   manifest.Implementation.Kind,
			ProducerService:        manifest.Implementation.ProducerService,
			Backend:                manifest.Implementation.Backend,
			Entrypoint:             manifest.Implementation.Entrypoint,
			ImplementationRevision: manifest.Implementation.ImplementationRevision,
			Config:                 model.NewJSONValue(manifest.Implementation.Config),
			Checksum:               manifest.Implementation.Checksum,
			IsCanonical:            true,
			Status:                 manifest.Implementation.Status,
		}
		if err := tx.Create(&implementation).Error; err != nil {
			return err
		}

		for i, spec := range manifest.Dependencies {
			dep, err := d.resolveDependencyTx(tx, version.ID, i, spec)
			if err != nil {
				return err
			}
			if err := tx.Create(dep).Error; err != nil {
				return err
			}
		}

		if err := d.validateGraphTx(tx); err != nil {
			return err
		}
		if manifest.Version.Status == "published" {
			if err := d.publishVersionTx(tx, definition.ID, &version); err != nil {
				return err
			}
		}
		return nil
	})
	return action, err
}

func (d *FeatureRegistryDao) resolveDependencyTx(tx *gorm.DB, versionID uint64, ordinal int, spec model.FeatureDependencySpec) (*model.FeatureDependency, error) {
	snapshot := model.NewJSONValue(spec)
	switch spec.Kind {
	case "feature":
		var upstream model.FeatureVersion
		err := tx.Table("govern.feature_version AS v").
			Select("v.*").
			Joins("JOIN govern.feature_definition d ON d.id = v.feature_id").
			Where("d.feature_code = ? AND v.version_number = ?", spec.FeatureCode, spec.FeatureVersion).
			First(&upstream).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "DEPENDENCY_NOT_FOUND",
				"feature dependency %s@%d does not exist", spec.FeatureCode, spec.FeatureVersion)
		}
		if err != nil {
			return nil, err
		}
		return &model.FeatureDependency{
			FeatureVersionID:            versionID,
			DependencyKind:              "feature",
			DependsOnFeatureVersionID:   &upstream.ID,
			DependencyReferenceSnapshot: snapshot,
			Ordinal:                     ordinal,
		}, nil
	case "data_field":
		var field struct {
			ID         uint64
			Deprecated bool
		}
		err := tx.Table("govern.data_field_dictionary").
			Select("id, deprecated").
			Where("source = ? AND dataset = ? AND data_type = ? AND raw_field = ? AND contract_version = ?",
				spec.Source, spec.Dataset, spec.DataType, spec.RawField, spec.ContractVersion).
			Take(&field).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "DATA_FIELD_NOT_FOUND",
				"data field %s/%s/%s/%s@%s does not exist",
				spec.Source, spec.Dataset, spec.DataType, spec.RawField, spec.ContractVersion)
		}
		if err != nil {
			return nil, err
		}
		if field.Deprecated {
			return nil, model.NewFeatureError(model.FeatureErrorUnprocessable, "DATA_FIELD_DEPRECATED",
				"data field %s/%s/%s/%s@%s is deprecated",
				spec.Source, spec.Dataset, spec.DataType, spec.RawField, spec.ContractVersion)
		}
		return &model.FeatureDependency{
			FeatureVersionID:            versionID,
			DependencyKind:              "data_field",
			DataFieldDictionaryID:       &field.ID,
			DependencyReferenceSnapshot: snapshot,
			Ordinal:                     ordinal,
		}, nil
	default:
		return nil, model.NewFeatureError(model.FeatureErrorValidation, "DEPENDENCY_KIND_INVALID",
			"dependency kind %q is invalid", spec.Kind)
	}
}

func (d *FeatureRegistryDao) publishVersionTx(tx *gorm.DB, featureID uint64, version *model.FeatureVersion) error {
	if version.Status == "published" {
		return nil
	}
	if version.Status != "draft" {
		return model.NewFeatureError(model.FeatureErrorConflict, "FEATURE_VERSION_NOT_DRAFT",
			"feature version %d is %s and cannot be published", version.ID, version.Status)
	}
	var canonicalCount int64
	if err := tx.Model(&model.FeatureImplementation{}).
		Where("feature_version_id = ? AND is_canonical = TRUE AND status = 'active'", version.ID).
		Count(&canonicalCount).Error; err != nil {
		return err
	}
	if canonicalCount != 1 {
		return model.NewFeatureError(model.FeatureErrorUnprocessable, "CANONICAL_IMPLEMENTATION_MISSING",
			"feature version %d must have exactly one active canonical implementation", version.ID)
	}
	var unavailableDependencyIDs []uint64
	if err := tx.Table("govern.feature_dependency AS d").
		Select("d.depends_on_feature_version_id").
		Joins("JOIN govern.feature_version AS upstream ON upstream.id = d.depends_on_feature_version_id").
		Where("d.feature_version_id = ? AND d.dependency_kind = 'feature' AND upstream.status <> 'published'", version.ID).
		Order("d.depends_on_feature_version_id ASC").Pluck("d.depends_on_feature_version_id", &unavailableDependencyIDs).Error; err != nil {
		return err
	}
	if len(unavailableDependencyIDs) > 0 {
		return model.NewFeatureError(model.FeatureErrorUnprocessable, "DEPENDENCY_NOT_PUBLISHED",
			"feature version %d depends on non-published feature versions %v", version.ID, unavailableDependencyIDs)
	}
	if err := d.validateGraphTx(tx); err != nil {
		return err
	}
	now := time.Now().UTC()
	if err := tx.Model(version).Updates(map[string]any{
		"status":       "published",
		"published_at": now,
		"updated_at":   now,
	}).Error; err != nil {
		return err
	}
	version.Status = "published"
	version.PublishedAt = &now
	return tx.Model(&model.FeatureDefinition{}).Where("id = ?", featureID).
		Updates(map[string]any{"status": "active", "updated_at": now}).Error
}

func (d *FeatureRegistryDao) validateGraphTx(tx *gorm.DB) error {
	type edge struct {
		SourceID uint64 `gorm:"column:source_id"`
		TargetID uint64 `gorm:"column:target_id"`
	}
	var rows []edge
	if err := tx.Table("govern.feature_dependency").
		Select("feature_version_id AS source_id, depends_on_feature_version_id AS target_id").
		Where("dependency_kind = 'feature'").Scan(&rows).Error; err != nil {
		return err
	}
	edges := make(map[uint64][]uint64)
	for _, row := range rows {
		edges[row.SourceID] = append(edges[row.SourceID], row.TargetID)
	}
	if cycle := DetectFeatureDependencyCycle(edges); len(cycle) > 0 {
		parts := make([]string, len(cycle))
		for i, id := range cycle {
			parts[i] = fmt.Sprintf("%d", id)
		}
		return model.NewFeatureError(model.FeatureErrorUnprocessable, "DEPENDENCY_CYCLE",
			"feature dependency cycle detected: %s", strings.Join(parts, " -> "))
	}
	return nil
}

// DetectFeatureDependencyCycle returns one cycle path, including the repeated
// start node, or nil when the graph is acyclic.
func DetectFeatureDependencyCycle(edges map[uint64][]uint64) []uint64 {
	const (
		unseen = iota
		visiting
		done
	)
	state := make(map[uint64]int)
	stack := make([]uint64, 0)
	position := make(map[uint64]int)
	var cycle []uint64
	var visit func(uint64) bool
	visit = func(node uint64) bool {
		state[node] = visiting
		position[node] = len(stack)
		stack = append(stack, node)
		neighbors := append([]uint64(nil), edges[node]...)
		sort.Slice(neighbors, func(i, j int) bool { return neighbors[i] < neighbors[j] })
		for _, next := range neighbors {
			switch state[next] {
			case unseen:
				if visit(next) {
					return true
				}
			case visiting:
				start := position[next]
				cycle = append(cycle, stack[start:]...)
				cycle = append(cycle, next)
				return true
			}
		}
		stack = stack[:len(stack)-1]
		delete(position, node)
		state[node] = done
		return false
	}
	nodes := make([]uint64, 0, len(edges))
	for node := range edges {
		nodes = append(nodes, node)
	}
	sort.Slice(nodes, func(i, j int) bool { return nodes[i] < nodes[j] })
	for _, node := range nodes {
		if state[node] == unseen && visit(node) {
			return cycle
		}
	}
	return nil
}

func (d *FeatureRegistryDao) Publish(ctx context.Context, featureCode string, versionNumber int) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var definition model.FeatureDefinition
		if err := tx.Where("feature_code = ?", featureCode).First(&definition).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_NOT_FOUND", "feature %s was not found", featureCode)
			}
			return err
		}
		var version model.FeatureVersion
		if err := tx.Where("feature_id = ? AND version_number = ?", definition.ID, versionNumber).First(&version).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_VERSION_NOT_FOUND",
					"feature %s@%d was not found", featureCode, versionNumber)
			}
			return err
		}
		return d.publishVersionTx(tx, definition.ID, &version)
	})
}

func (d *FeatureRegistryDao) Deprecate(ctx context.Context, featureCode string, versionNumber int) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var definition model.FeatureDefinition
		if err := tx.Where("feature_code = ?", featureCode).First(&definition).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_NOT_FOUND", "feature %s was not found", featureCode)
			}
			return err
		}
		var version model.FeatureVersion
		if err := tx.Where("feature_id = ? AND version_number = ?", definition.ID, versionNumber).First(&version).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_VERSION_NOT_FOUND",
					"feature %s@%d was not found", featureCode, versionNumber)
			}
			return err
		}
		if version.Status == "deprecated" {
			return nil
		}
		if version.Status != "published" {
			return model.NewFeatureError(model.FeatureErrorConflict, "FEATURE_VERSION_NOT_PUBLISHED",
				"feature %s@%d is %s and cannot be deprecated", featureCode, versionNumber, version.Status)
		}
		now := time.Now().UTC()
		if err := tx.Model(&version).Updates(map[string]any{
			"status": "deprecated", "deprecated_at": now, "updated_at": now,
		}).Error; err != nil {
			return err
		}
		var publishedCount int64
		if err := tx.Model(&model.FeatureVersion{}).
			Where("feature_id = ? AND status = 'published'", definition.ID).Count(&publishedCount).Error; err != nil {
			return err
		}
		if publishedCount == 0 {
			return tx.Model(&definition).Updates(map[string]any{"status": "deprecated", "updated_at": now}).Error
		}
		return nil
	})
}

func (d *FeatureRegistryDao) ListDefinitions(ctx context.Context, status, category, owner string, limit, offset int) ([]model.FeatureDefinition, int64, error) {
	q := d.db.WithContext(ctx).Model(&model.FeatureDefinition{})
	if status != "" {
		q = q.Where("status = ?", status)
	}
	if category != "" {
		q = q.Where("category = ?", category)
	}
	if owner != "" {
		q = q.Where("owner = ?", owner)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []model.FeatureDefinition
	q = q.Order("feature_code ASC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	if err := q.Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (d *FeatureRegistryDao) GetDefinitionDetail(ctx context.Context, featureCode string) (*model.FeatureDefinitionDetail, error) {
	var definition model.FeatureDefinition
	if err := d.db.WithContext(ctx).Where("feature_code = ?", featureCode).First(&definition).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_NOT_FOUND", "feature %s was not found", featureCode)
		}
		return nil, err
	}
	var versions []model.FeatureVersion
	if err := d.db.WithContext(ctx).Where("feature_id = ?", definition.ID).Order("version_number DESC").Find(&versions).Error; err != nil {
		return nil, err
	}
	summaries := make([]model.FeatureVersionSummary, 0, len(versions))
	for _, version := range versions {
		var implementations []model.FeatureImplementation
		var dependencies []model.FeatureDependency
		if err := d.db.WithContext(ctx).Where("feature_version_id = ?", version.ID).Order("id ASC").Find(&implementations).Error; err != nil {
			return nil, err
		}
		if err := d.db.WithContext(ctx).Where("feature_version_id = ?", version.ID).Order("ordinal ASC, id ASC").Find(&dependencies).Error; err != nil {
			return nil, err
		}
		summaries = append(summaries, model.FeatureVersionSummary{Version: version, Implementations: implementations, Dependencies: dependencies})
	}
	return &model.FeatureDefinitionDetail{Definition: definition, Versions: summaries}, nil
}

func (d *FeatureRegistryDao) GetVersionSummary(ctx context.Context, versionID uint64) (*model.FeatureVersionSummary, error) {
	var version model.FeatureVersion
	if err := d.db.WithContext(ctx).First(&version, versionID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_VERSION_NOT_FOUND", "feature version %d was not found", versionID)
		}
		return nil, err
	}
	var implementations []model.FeatureImplementation
	var dependencies []model.FeatureDependency
	if err := d.db.WithContext(ctx).Where("feature_version_id = ?", versionID).Order("id ASC").Find(&implementations).Error; err != nil {
		return nil, err
	}
	if err := d.db.WithContext(ctx).Where("feature_version_id = ?", versionID).Order("ordinal ASC, id ASC").Find(&dependencies).Error; err != nil {
		return nil, err
	}
	return &model.FeatureVersionSummary{Version: version, Implementations: implementations, Dependencies: dependencies}, nil
}

func (d *FeatureRegistryDao) GetLineage(ctx context.Context, featureCode string) (*model.FeatureLineage, error) {
	detail, err := d.GetDefinitionDetail(ctx, featureCode)
	if err != nil {
		return nil, err
	}
	result := &model.FeatureLineage{FeatureCode: featureCode, Versions: make([]model.FeatureLineageVersion, 0, len(detail.Versions))}
	for _, summary := range detail.Versions {
		var downstream []model.FeatureDependency
		if err := d.db.WithContext(ctx).Where("depends_on_feature_version_id = ?", summary.Version.ID).
			Order("feature_version_id ASC, ordinal ASC").Find(&downstream).Error; err != nil {
			return nil, err
		}
		upstreamFeatures, err := d.lineageFeatureReferences(ctx, summary.Version.ID, false)
		if err != nil {
			return nil, err
		}
		downstreamFeatures, err := d.lineageFeatureReferences(ctx, summary.Version.ID, true)
		if err != nil {
			return nil, err
		}
		dataFields, err := d.lineageDataFields(ctx, summary.Version.ID)
		if err != nil {
			return nil, err
		}
		result.Versions = append(result.Versions, model.FeatureLineageVersion{
			FeatureVersionID:   summary.Version.ID,
			VersionNumber:      summary.Version.VersionNumber,
			Upstream:           summary.Dependencies,
			Downstream:         downstream,
			UpstreamFeatures:   upstreamFeatures,
			DownstreamFeatures: downstreamFeatures,
			UpstreamDataFields: dataFields,
		})
	}
	return result, nil
}

func (d *FeatureRegistryDao) lineageFeatureReferences(ctx context.Context, versionID uint64, downstream bool) ([]model.FeatureLineageReference, error) {
	query := `
		WITH RECURSIVE related(id) AS (
			SELECT depends_on_feature_version_id
			FROM govern.feature_dependency
			WHERE feature_version_id = ? AND dependency_kind = 'feature'
			UNION
			SELECT dependency.depends_on_feature_version_id
			FROM govern.feature_dependency AS dependency
			JOIN related ON related.id = dependency.feature_version_id
			WHERE dependency.dependency_kind = 'feature'
		)
		SELECT version.id AS feature_version_id, definition.feature_code,
		       version.version_number, version.status
		FROM related
		JOIN govern.feature_version AS version ON version.id = related.id
		JOIN govern.feature_definition AS definition ON definition.id = version.feature_id
		ORDER BY definition.feature_code, version.version_number, version.id`
	if downstream {
		query = `
			WITH RECURSIVE related(id) AS (
				SELECT feature_version_id
				FROM govern.feature_dependency
				WHERE depends_on_feature_version_id = ? AND dependency_kind = 'feature'
				UNION
				SELECT dependency.feature_version_id
				FROM govern.feature_dependency AS dependency
				JOIN related ON related.id = dependency.depends_on_feature_version_id
				WHERE dependency.dependency_kind = 'feature'
			)
			SELECT version.id AS feature_version_id, definition.feature_code,
			       version.version_number, version.status
			FROM related
			JOIN govern.feature_version AS version ON version.id = related.id
			JOIN govern.feature_definition AS definition ON definition.id = version.feature_id
			ORDER BY definition.feature_code, version.version_number, version.id`
	}
	rows := make([]model.FeatureLineageReference, 0)
	if err := d.db.WithContext(ctx).Raw(query, versionID).Scan(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (d *FeatureRegistryDao) lineageDataFields(ctx context.Context, versionID uint64) ([]model.FeatureLineageDataField, error) {
	rows := make([]model.FeatureLineageDataField, 0)
	err := d.db.WithContext(ctx).Raw(`
		WITH RECURSIVE upstream(id) AS (
			SELECT ?::bigint
			UNION
			SELECT dependency.depends_on_feature_version_id
			FROM govern.feature_dependency AS dependency
			JOIN upstream ON upstream.id = dependency.feature_version_id
			WHERE dependency.dependency_kind = 'feature'
		)
		SELECT DISTINCT field.id AS data_field_dictionary_id, field.source, field.dataset,
		       field.data_type, field.raw_field, field.contract_version,
		       field.storage_location, field.deprecated
		FROM upstream
		JOIN govern.feature_dependency AS dependency
		  ON dependency.feature_version_id = upstream.id
		 AND dependency.dependency_kind = 'data_field'
		JOIN govern.data_field_dictionary AS field
		  ON field.id = dependency.data_field_dictionary_id
		ORDER BY field.source, field.dataset, field.data_type, field.raw_field,
		         field.contract_version`, versionID).Scan(&rows).Error
	return rows, err
}

func (d *FeatureRegistryDao) GetAvailability(ctx context.Context, featureCode, sourceProfile string) (*model.FeatureAvailability, error) {
	var definition model.FeatureDefinition
	if err := d.db.WithContext(ctx).Where("feature_code = ?", featureCode).First(&definition).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_NOT_FOUND", "feature %s was not found", featureCode)
		}
		return nil, err
	}
	if sourceProfile == "" {
		sourceProfile = "default"
	}
	availability := &model.FeatureAvailability{
		FeatureCode: featureCode, SourceProfile: sourceProfile, Status: "unavailable",
		DefinitionStatus: "valid", VersionStatus: "draft", DependencyStatus: "unknown",
		DataStatus: "unknown", ImplementationStatus: "unloadable",
		MaterializationStatus: "never", ExecutionReadiness: "not_ready",
		Reasons: make([]string, 0), DataFields: make([]model.FeatureDataFieldAvailability, 0),
	}
	if definition.FeatureCode == "" || definition.EntityType == "" || definition.ValueType == "" {
		availability.DefinitionStatus = "invalid"
		availability.Reasons = append(availability.Reasons, "definition is incomplete")
	}
	var version model.FeatureVersion
	err := d.db.WithContext(ctx).Where("feature_id = ? AND status = 'published'", definition.ID).
		Order("version_number DESC").First(&version).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		if latestErr := d.db.WithContext(ctx).Where("feature_id = ?", definition.ID).
			Order("version_number DESC").First(&version).Error; latestErr == nil {
			availability.VersionStatus = version.Status
		}
		availability.Reasons = append(availability.Reasons, "no published feature version")
		return availability, nil
	}
	if err != nil {
		return nil, err
	}
	availability.LatestPublishedID = &version.ID
	availability.VersionStatus = version.Status
	availability.Status = "registered"

	upstream, err := d.lineageFeatureReferences(ctx, version.ID, false)
	if err != nil {
		return nil, err
	}
	dataFields, err := d.lineageDataFields(ctx, version.ID)
	if err != nil {
		return nil, err
	}
	availability.DependencyStatus = "ready"
	dependencyEdges, err := d.dependencyEdges(ctx, version.ID)
	if err != nil {
		return nil, err
	}
	if len(DetectFeatureDependencyCycle(dependencyEdges)) > 0 {
		availability.DependencyStatus = "cycle"
		availability.Reasons = append(availability.Reasons, "feature dependency graph contains a cycle")
	}
	for _, dependency := range upstream {
		if dependency.Status != "published" {
			if availability.DependencyStatus != "cycle" {
				availability.DependencyStatus = "missing"
			}
			availability.Reasons = append(availability.Reasons,
				fmt.Sprintf("upstream %s@%d is %s", dependency.FeatureCode, dependency.VersionNumber, dependency.Status))
		}
	}

	readyFields, unknownFields := 0, 0
	for _, field := range dataFields {
		item := model.FeatureDataFieldAvailability{FeatureLineageDataField: field, Status: "unknown"}
		if field.Deprecated {
			item.Status = "missing"
			if availability.DependencyStatus != "cycle" {
				availability.DependencyStatus = "missing"
			}
			availability.Reasons = append(availability.Reasons,
				fmt.Sprintf("data field %s/%s/%s is deprecated", field.Source, field.Dataset, field.RawField))
		} else if field.StorageLocation == "top_level" {
			item.Status = "ready"
			readyFields++
		} else {
			var observation struct {
				Status      string
				SampleCount int64
				LastSeenAt  time.Time
			}
			observationErr := d.db.WithContext(ctx).Table("govern.data_field_coverage_observation").
				Select("status, sample_count, last_seen_at").
				Where("source = ? AND dataset = ? AND observed_key = ?", field.Source, field.Dataset, field.RawField).
				Take(&observation).Error
			if observationErr == nil && observation.Status == "governed" && observation.SampleCount > 0 {
				item.Status = "ready"
				item.SampleCount = observation.SampleCount
				item.LastSeenAt = &observation.LastSeenAt
				readyFields++
			} else if observationErr != nil && !errors.Is(observationErr, gorm.ErrRecordNotFound) {
				return nil, observationErr
			} else {
				unknownFields++
			}
		}
		availability.DataFields = append(availability.DataFields, item)
	}
	availability.DataStatus = featureDataStatus(availability.DataFields, readyFields, unknownFields)

	var implementations []model.FeatureImplementation
	if err := d.db.WithContext(ctx).Where("feature_version_id = ? AND is_canonical = TRUE", version.ID).
		Order("id ASC").Find(&implementations).Error; err != nil {
		return nil, err
	}
	availability.ImplementationStatus = featureImplementationStatus(implementations)

	var latestRun model.FeatureRun
	latestErr := d.db.WithContext(ctx).Table("govern.feature_run AS run").Select("run.*").
		Joins("JOIN govern.feature_run_item AS item ON item.run_id = run.run_id").
		Where("item.feature_version_id = ?", version.ID).
		Order("CASE WHEN run.status IN ('queued', 'planning', 'running', 'validating') THEN 0 ELSE 1 END").
		Order("COALESCE(run.finished_at, run.updated_at, run.created_at) DESC, run.created_at DESC").
		First(&latestRun).Error
	if latestErr != nil && !errors.Is(latestErr, gorm.ErrRecordNotFound) {
		return nil, latestErr
	}
	var latestSucceeded model.FeatureRun
	succeededErr := d.db.WithContext(ctx).Table("govern.feature_run AS run").Select("run.*").
		Joins("JOIN govern.feature_run_item AS item ON item.run_id = run.run_id").
		Where("item.feature_version_id = ? AND item.status = 'succeeded' AND run.status = 'succeeded'", version.ID).
		Order("run.as_of_time DESC, run.created_at DESC").First(&latestSucceeded).Error
	if succeededErr == nil {
		availability.LatestSucceededRun = &latestSucceeded
		availability.Status = "available"
	} else if !errors.Is(succeededErr, gorm.ErrRecordNotFound) {
		return nil, succeededErr
	}
	availability.MaterializationStatus = featureMaterializationStatus(latestErr, latestRun.Status, succeededErr)

	availability.ExecutionReadiness = featureExecutionReadiness(
		definition, availability.DefinitionStatus, availability.VersionStatus,
		availability.DependencyStatus, availability.DataStatus, availability.ImplementationStatus,
	)
	if availability.DependencyStatus != "ready" {
		availability.Reasons = append(availability.Reasons, "dependencies are not ready")
	}
	if availability.DataStatus != "ready" {
		availability.Reasons = append(availability.Reasons, "source data availability is "+availability.DataStatus)
	}
	if availability.ImplementationStatus != "loadable" {
		availability.Reasons = append(availability.Reasons, "implementation is "+availability.ImplementationStatus)
	}
	if definition.EntityType != "security" {
		availability.Reasons = append(availability.Reasons, "entity_type is not executable in this release")
	}
	if definition.ValueType != "number" && definition.ValueType != "integer" {
		availability.Reasons = append(availability.Reasons, "value_type is not executable in this release")
	}
	return availability, nil
}

func (d *FeatureRegistryDao) dependencyEdges(ctx context.Context, versionID uint64) (map[uint64][]uint64, error) {
	type edge struct {
		SourceID uint64 `gorm:"column:source_id"`
		TargetID uint64 `gorm:"column:target_id"`
	}
	rows := make([]edge, 0)
	err := d.db.WithContext(ctx).Raw(`
		WITH RECURSIVE upstream(id) AS (
			SELECT ?::bigint
			UNION
			SELECT dependency.depends_on_feature_version_id
			FROM govern.feature_dependency AS dependency
			JOIN upstream ON upstream.id = dependency.feature_version_id
			WHERE dependency.dependency_kind = 'feature'
		)
		SELECT dependency.feature_version_id AS source_id,
		       dependency.depends_on_feature_version_id AS target_id
		FROM govern.feature_dependency AS dependency
		JOIN upstream ON upstream.id = dependency.feature_version_id
		WHERE dependency.dependency_kind = 'feature'
		ORDER BY dependency.feature_version_id, dependency.depends_on_feature_version_id`, versionID).
		Scan(&rows).Error
	if err != nil {
		return nil, err
	}
	edges := make(map[uint64][]uint64)
	for _, row := range rows {
		edges[row.SourceID] = append(edges[row.SourceID], row.TargetID)
	}
	return edges, nil
}

func featureDataStatus(fields []model.FeatureDataFieldAvailability, ready, unknown int) string {
	if len(fields) == 0 {
		return "ready"
	}
	missing := 0
	for _, field := range fields {
		if field.Status == "missing" {
			missing++
		}
	}
	if missing == len(fields) {
		return "missing"
	}
	if missing > 0 || (ready > 0 && unknown > 0) {
		return "partial"
	}
	if ready == len(fields) {
		return "ready"
	}
	return "unknown"
}

func featureImplementationStatus(rows []model.FeatureImplementation) string {
	if len(rows) != 1 {
		return "unloadable"
	}
	implementation := rows[0]
	if implementation.Status != "active" {
		return "disabled"
	}
	if implementation.Kind != "python" || implementation.ProducerService != "artemis" {
		return "unsupported"
	}
	if strings.TrimSpace(implementation.Entrypoint) == "" {
		return "unloadable"
	}
	return "loadable"
}

func featureMaterializationStatus(latestErr error, latestStatus string, succeededErr error) string {
	if errors.Is(latestErr, gorm.ErrRecordNotFound) {
		return "never"
	}
	if latestErr != nil {
		return "failed"
	}
	switch latestStatus {
	case "queued", "planning", "running", "validating":
		return "running"
	case "succeeded":
		return "succeeded"
	default:
		if succeededErr == nil {
			return "stale"
		}
		return "failed"
	}
}

func featureExecutionReadiness(
	definition model.FeatureDefinition,
	definitionStatus, versionStatus, dependencyStatus, dataStatus, implementationStatus string,
) string {
	if definitionStatus != "valid" || versionStatus != "published" || dependencyStatus != "ready" ||
		implementationStatus != "loadable" || definition.EntityType != "security" ||
		(definition.ValueType != "number" && definition.ValueType != "integer") {
		return "not_ready"
	}
	if dataStatus == "unknown" {
		return "unknown"
	}
	if dataStatus != "ready" {
		return "not_ready"
	}
	return "ready"
}

func (d *FeatureRegistryDao) ValidatePublishedVersionIDs(ctx context.Context, ids []uint64) error {
	if len(ids) == 0 {
		return model.NewFeatureError(model.FeatureErrorValidation, "FEATURE_VERSION_REQUIRED", "at least one feature version is required")
	}
	var rows []model.FeatureVersion
	if err := d.db.WithContext(ctx).Where("id IN ?", ids).Find(&rows).Error; err != nil {
		return err
	}
	byID := make(map[uint64]model.FeatureVersion, len(rows))
	for _, row := range rows {
		byID[row.ID] = row
	}
	for _, id := range ids {
		row, ok := byID[id]
		if !ok {
			return model.NewFeatureError(model.FeatureErrorUnprocessable, "FEATURE_VERSION_NOT_FOUND", "feature version %d was not found", id)
		}
		if row.Status != "published" {
			return model.NewFeatureError(model.FeatureErrorUnprocessable, "FEATURE_VERSION_NOT_PUBLISHED",
				"feature version %d is %s, expected published", id, row.Status)
		}
	}
	return nil
}

// ResolveExecutionVersionIDs returns the root versions and every transitive
// Feature dependency as a stable, sorted set. Data-field dependencies are not
// RunItems and are intentionally excluded.
func (d *FeatureRegistryDao) ResolveExecutionVersionIDs(ctx context.Context, rootIDs []uint64) ([]uint64, error) {
	roots := make(model.Int64Array, len(rootIDs))
	for i, id := range rootIDs {
		roots[i] = int64(id)
	}
	var ids []uint64
	err := d.db.WithContext(ctx).Raw(`
		WITH RECURSIVE execution_versions(id) AS (
			SELECT UNNEST(?::bigint[])
			UNION
			SELECT dependency.depends_on_feature_version_id
			FROM govern.feature_dependency AS dependency
			JOIN execution_versions AS current
			  ON current.id = dependency.feature_version_id
			WHERE dependency.dependency_kind = 'feature'
		)
		SELECT id FROM execution_versions ORDER BY id`, roots).Scan(&ids).Error
	if err != nil {
		return nil, err
	}
	if err := d.ValidatePublishedVersionIDs(ctx, ids); err != nil {
		return nil, err
	}
	return ids, nil
}

func (d *FeatureRegistryDao) VersionRequiresSourceAvailability(ctx context.Context, versionID uint64) (bool, error) {
	var count int64
	err := d.db.WithContext(ctx).Raw(`
		WITH RECURSIVE dependency_versions(id) AS (
			SELECT ?::bigint
			UNION
			SELECT d.depends_on_feature_version_id
			FROM govern.feature_dependency d
			JOIN dependency_versions v ON v.id = d.feature_version_id
			WHERE d.dependency_kind = 'feature'
		)
		SELECT COUNT(*)
		FROM govern.feature_dependency d
		JOIN dependency_versions v ON v.id = d.feature_version_id
		WHERE d.dependency_kind = 'data_field'`, versionID).Scan(&count).Error
	return count > 0, err
}
