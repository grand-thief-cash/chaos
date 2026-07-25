package dao

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type FeaturePurgeImpact struct {
	Targets              []model.FeatureDataPurgeTarget
	EstimatedRows        int64
	AffectedRunCount     int
	AffectedVersionCount int
	AffectsLatest        bool
	ObservedFrom         *time.Time
	ObservedTo           *time.Time
}

func (d *FeatureRunDao) BuildPurgeImpact(
	ctx context.Context,
	req model.FeaturePurgePreviewRequest,
) (map[string]any, *FeaturePurgeImpact, error) {
	criteria := map[string]any{"scope_type": req.ScopeType}
	joinValues := `LEFT JOIN dwd.feature_value_numeric AS value
		ON value.run_id = item.run_id AND value.feature_version_id = item.feature_version_id`
	query := d.db.WithContext(ctx).Table("govern.feature_run_item AS item").
		Select(`item.run_id, item.feature_version_id, COUNT(value.run_id) AS estimated_rows,
		        MIN(value.observed_at) AS observed_from, MAX(value.observed_at) AS observed_to`).
		Joins(joinValues).
		Joins("JOIN govern.feature_run AS run ON run.run_id = item.run_id").
		Where("item.materialization_state = 'available' AND item.status = 'succeeded' AND run.status IN ('succeeded','partially_succeeded')")

	switch req.ScopeType {
	case "run":
		criteria["run_id"] = req.RunID
		var run model.FeatureRun
		if err := d.db.WithContext(ctx).Where("run_id = ?", req.RunID).First(&run).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return nil, nil, model.NewFeatureError(model.FeatureErrorNotFound, "RUN_NOT_FOUND", "feature run %s was not found", req.RunID)
			}
			return nil, nil, err
		}
		if isActivePurgeRunStatus(run.Status) {
			return nil, nil, model.NewFeatureError(model.FeatureErrorConflict, "PURGE_ACTIVE_RUN_FORBIDDEN", "active run %s cannot be purged", req.RunID)
		}
		query = query.Where("item.run_id = ?", req.RunID)
	case "feature_version":
		criteria["feature_version_id"] = req.FeatureVersionID
		var count int64
		if err := d.db.WithContext(ctx).Model(&model.FeatureVersion{}).
			Where("id = ?", req.FeatureVersionID).Count(&count).Error; err != nil {
			return nil, nil, err
		}
		if count == 0 {
			return nil, nil, model.NewFeatureError(model.FeatureErrorNotFound, "FEATURE_VERSION_NOT_FOUND", "feature version %d was not found", req.FeatureVersionID)
		}
		query = query.Where("item.feature_version_id = ?", req.FeatureVersionID)
	case "feature_all_versions":
		criteria["feature_code"] = req.FeatureCode
		criteria["all_versions"] = true
		if !req.AllVersions {
			return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "ALL_VERSIONS_CONFIRMATION_REQUIRED", "all_versions must be explicitly true")
		}
		query = query.Joins("JOIN govern.feature_version AS version ON version.id = item.feature_version_id").
			Joins("JOIN govern.feature_definition AS definition ON definition.id = version.feature_id").
			Where("definition.feature_code = ?", req.FeatureCode)
	default:
		return nil, nil, model.NewFeatureError(model.FeatureErrorValidation, "PURGE_SCOPE_INVALID", "scope_type %q is invalid", req.ScopeType)
	}

	type impactRow struct {
		RunID            string
		FeatureVersionID uint64
		EstimatedRows    int64
		ObservedFrom     *time.Time
		ObservedTo       *time.Time
	}
	var rows []impactRow
	if err := query.Group("item.run_id, item.feature_version_id").
		Order("item.run_id, item.feature_version_id").Scan(&rows).Error; err != nil {
		return nil, nil, err
	}
	impact := &FeaturePurgeImpact{Targets: make([]model.FeatureDataPurgeTarget, 0, len(rows))}
	runIDs := make(map[string]struct{})
	versionIDs := make(map[uint64]struct{})
	for _, row := range rows {
		impact.EstimatedRows += row.EstimatedRows
		runIDs[row.RunID] = struct{}{}
		versionIDs[row.FeatureVersionID] = struct{}{}
		if row.ObservedFrom != nil && (impact.ObservedFrom == nil || row.ObservedFrom.Before(*impact.ObservedFrom)) {
			impact.ObservedFrom = row.ObservedFrom
		}
		if row.ObservedTo != nil && (impact.ObservedTo == nil || row.ObservedTo.After(*impact.ObservedTo)) {
			impact.ObservedTo = row.ObservedTo
		}
		impact.Targets = append(impact.Targets, model.FeatureDataPurgeTarget{
			RunID: row.RunID, FeatureVersionID: row.FeatureVersionID,
			Status: "pending", EstimatedRows: row.EstimatedRows,
		})
	}
	impact.AffectedRunCount = len(runIDs)
	impact.AffectedVersionCount = len(versionIDs)
	var err error
	impact.AffectsLatest, err = d.targetsAffectLatest(ctx, impact.Targets)
	if err != nil {
		return nil, nil, err
	}
	return criteria, impact, nil
}

func isActivePurgeRunStatus(status string) bool {
	switch status {
	case "queued", "planning", "running", "validating":
		return true
	default:
		return false
	}
}

func (d *FeatureRunDao) targetsAffectLatest(
	ctx context.Context,
	targets []model.FeatureDataPurgeTarget,
) (bool, error) {
	if len(targets) == 0 {
		return false, nil
	}
	type latestRow struct {
		RunID            string
		FeatureVersionID uint64
	}
	var latest []latestRow
	if err := d.db.WithContext(ctx).Raw(`
		SELECT DISTINCT ON (item.feature_version_id)
		       item.run_id, item.feature_version_id
		FROM govern.feature_run_item AS item
		JOIN govern.feature_run AS run ON run.run_id = item.run_id
		WHERE item.materialization_state = 'available'
		  AND item.status = 'succeeded' AND run.status = 'succeeded'
		ORDER BY item.feature_version_id, run.as_of_time DESC, run.created_at DESC`).Scan(&latest).Error; err != nil {
		return false, err
	}
	targetKeys := make(map[string]struct{}, len(targets))
	for _, target := range targets {
		targetKeys[fmt.Sprintf("%s/%d", target.RunID, target.FeatureVersionID)] = struct{}{}
	}
	for _, row := range latest {
		if _, ok := targetKeys[fmt.Sprintf("%s/%d", row.RunID, row.FeatureVersionID)]; ok {
			return true, nil
		}
	}
	return false, nil
}

func (d *FeatureRunDao) CreatePurgePreview(
	ctx context.Context,
	job *model.FeatureDataPurgeJob,
	targets []model.FeatureDataPurgeTarget,
) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(job).Error; err != nil {
			return err
		}
		if len(targets) == 0 {
			return nil
		}
		return tx.CreateInBatches(targets, 500).Error
	})
}

func (d *FeatureRunDao) GetPurge(
	ctx context.Context,
	purgeID string,
) (*model.FeatureDataPurgeJob, []model.FeatureDataPurgeTarget, error) {
	var job model.FeatureDataPurgeJob
	if err := d.db.WithContext(ctx).Where("purge_id = ?", purgeID).First(&job).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil, model.NewFeatureError(model.FeatureErrorNotFound, "PURGE_NOT_FOUND", "purge %s was not found", purgeID)
		}
		return nil, nil, err
	}
	var targets []model.FeatureDataPurgeTarget
	if err := d.db.WithContext(ctx).Where("purge_id = ?", purgeID).
		Order("run_id, feature_version_id").Find(&targets).Error; err != nil {
		return nil, nil, err
	}
	return &job, targets, nil
}

func (d *FeatureRunDao) ListPurges(
	ctx context.Context,
	f model.FeaturePurgeFilters,
	limit, offset int,
) ([]model.FeatureDataPurgeJob, int64, error) {
	query := d.db.WithContext(ctx).Model(&model.FeatureDataPurgeJob{})
	if f.Status != "" {
		query = query.Where("status = ?", f.Status)
	}
	if f.ScopeType != "" {
		query = query.Where("scope_type = ?", f.ScopeType)
	}
	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var jobs []model.FeatureDataPurgeJob
	if err := query.Order("created_at DESC").Limit(limit).Offset(offset).Find(&jobs).Error; err != nil {
		return nil, 0, err
	}
	return jobs, total, nil
}

func (d *FeatureRunDao) QueuePurge(
	ctx context.Context,
	job *model.FeatureDataPurgeJob,
) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Model(&model.FeatureDataPurgeJob{}).
			Where("purge_id = ? AND status = 'previewed'", job.PurgeID).
			Updates(map[string]any{
				"status": "queued", "updated_at": gorm.Expr("NOW()"),
			})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected != 1 {
			return model.NewFeatureError(model.FeatureErrorConflict, "PURGE_STATE_CONFLICT", "purge %s is no longer previewed", job.PurgeID)
		}
		return d.createPurgeLifecycleEvents(tx, job.PurgeID, "purge_create", "available", "purging")
	})
}

func (d *FeatureRunDao) CancelPurge(ctx context.Context, purgeID string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var job model.FeatureDataPurgeJob
		if err := tx.Where("purge_id = ?", purgeID).First(&job).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return model.NewFeatureError(model.FeatureErrorNotFound, "PURGE_NOT_FOUND", "purge %s was not found", purgeID)
			}
			return err
		}
		res := tx.Model(&model.FeatureDataPurgeJob{}).
			Where("purge_id = ? AND status IN ?", purgeID, []string{"previewed", "queued"}).
			Updates(map[string]any{"status": "cancelled", "finished_at": gorm.Expr("NOW()"), "updated_at": gorm.Expr("NOW()")})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected != 1 {
			return model.NewFeatureError(model.FeatureErrorConflict, "PURGE_STATE_CONFLICT", "purge %s can no longer be cancelled", purgeID)
		}
		if err := tx.Model(&model.FeatureDataPurgeTarget{}).Where("purge_id = ? AND status = 'pending'", purgeID).
			Updates(map[string]any{"status": "cancelled", "finished_at": gorm.Expr("NOW()")}).Error; err != nil {
			return err
		}
		return d.createPurgeLifecycleEvents(tx, purgeID, "purge_cancel", job.Status, "cancelled")
	})
}

func (d *FeatureRunDao) ProcessNextPurgeTarget(ctx context.Context) (bool, string, error) {
	processed := false
	purgeID := ""
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("SELECT pg_advisory_xact_lock(hashtextextended('feature-purge-worker', 0))").Error; err != nil {
			return err
		}
		var job model.FeatureDataPurgeJob
		err := tx.Clauses(clause.Locking{Strength: "UPDATE", Options: "SKIP LOCKED"}).
			Where("status IN ?", []string{"running", "queued"}).
			Order("CASE WHEN status = 'running' THEN 0 ELSE 1 END, created_at").
			First(&job).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil
		}
		if err != nil {
			return err
		}
		processed = true
		purgeID = job.PurgeID
		if job.Status == "queued" {
			now := time.Now().UTC()
			if err := tx.Model(&model.FeatureDataPurgeJob{}).Where("purge_id = ?", job.PurgeID).
				Updates(map[string]any{"status": "running", "started_at": now, "updated_at": now}).Error; err != nil {
				return err
			}
			job.Status = "running"
		}
		var target model.FeatureDataPurgeTarget
		err = tx.Clauses(clause.Locking{Strength: "UPDATE", Options: "SKIP LOCKED"}).
			Where("purge_id = ? AND status = 'pending'", job.PurgeID).
			Order("run_id, feature_version_id").First(&target).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return d.finishPurgeTx(tx, &job)
		}
		if err != nil {
			return err
		}
		return d.executePurgeTargetTx(tx, &job, &target)
	})
	return processed, purgeID, err
}

func (d *FeatureRunDao) executePurgeTargetTx(
	tx *gorm.DB,
	job *model.FeatureDataPurgeJob,
	target *model.FeatureDataPurgeTarget,
) error {
	now := time.Now().UTC()
	if err := tx.Model(&model.FeatureDataPurgeTarget{}).
		Where("purge_id = ? AND run_id = ? AND feature_version_id = ?", target.PurgeID, target.RunID, target.FeatureVersionID).
		Updates(map[string]any{"status": "running", "started_at": now}).Error; err != nil {
		return err
	}
	if err := tx.Model(&model.FeatureRunItem{}).
		Where("run_id = ? AND feature_version_id = ? AND materialization_state = 'available'", target.RunID, target.FeatureVersionID).
		Update("materialization_state", "purging").Error; err != nil {
		return err
	}
	if err := tx.Exec("SELECT set_config('feature_platform.purge_id', ?, TRUE)", job.PurgeID).Error; err != nil {
		return err
	}
	deleteQuery := tx.Where("run_id = ? AND feature_version_id = ?", target.RunID, target.FeatureVersionID)
	result := deleteQuery.Delete(&model.FeatureNumericValue{})
	if result.Error != nil {
		return result.Error
	}
	var remaining int64
	if err := tx.Model(&model.FeatureNumericValue{}).
		Where("run_id = ? AND feature_version_id = ?", target.RunID, target.FeatureVersionID).
		Count(&remaining).Error; err != nil {
		return err
	}
	state := "available"
	var purgedAt any
	if remaining == 0 {
		state = "purged"
		purgedAt = now
	}
	if err := tx.Model(&model.FeatureRunItem{}).
		Where("run_id = ? AND feature_version_id = ?", target.RunID, target.FeatureVersionID).
		Updates(map[string]any{
			"materialization_state": state, "materialized_row_count": remaining,
			"purged_at": purgedAt, "last_purge_id": job.PurgeID,
		}).Error; err != nil {
		return err
	}
	if err := tx.Model(&model.FeatureDataPurgeTarget{}).
		Where("purge_id = ? AND run_id = ? AND feature_version_id = ?", target.PurgeID, target.RunID, target.FeatureVersionID).
		Updates(map[string]any{
			"status": "succeeded", "deleted_rows": result.RowsAffected,
			"finished_at": now,
		}).Error; err != nil {
		return err
	}
	return tx.Model(&model.FeatureDataPurgeJob{}).Where("purge_id = ?", job.PurgeID).
		Updates(map[string]any{
			"deleted_rows": gorm.Expr("deleted_rows + ?", result.RowsAffected),
			"updated_at":   now,
		}).Error
}

func (d *FeatureRunDao) finishPurgeTx(tx *gorm.DB, job *model.FeatureDataPurgeJob) error {
	now := time.Now().UTC()
	if err := tx.Model(&model.FeatureDataPurgeJob{}).Where("purge_id = ? AND status = 'running'", job.PurgeID).
		Updates(map[string]any{"status": "succeeded", "finished_at": now, "updated_at": now}).Error; err != nil {
		return err
	}
	return d.createPurgeLifecycleEvents(tx, job.PurgeID, "purge_complete", "purging", "purged")
}

func (d *FeatureRunDao) FailPurge(ctx context.Context, purgeID string, cause error) error {
	message := cause.Error()
	if len(message) > 2000 {
		message = message[:2000]
	}
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var job model.FeatureDataPurgeJob
		if err := tx.Where("purge_id = ?", purgeID).First(&job).Error; err != nil {
			return err
		}
		if err := tx.Model(&model.FeatureDataPurgeJob{}).Where("purge_id = ?", purgeID).
			Updates(map[string]any{
				"status": "failed", "finished_at": gorm.Expr("NOW()"),
				"error_summary": model.NewJSONValue(map[string]any{"message": message}),
				"updated_at":    gorm.Expr("NOW()"),
			}).Error; err != nil {
			return err
		}
		if err := tx.Model(&model.FeatureDataPurgeTarget{}).
			Where("purge_id = ? AND status IN ?", purgeID, []string{"pending", "running"}).
			Updates(map[string]any{
				"status": "failed", "finished_at": gorm.Expr("NOW()"),
				"error_message": message,
			}).Error; err != nil {
			return err
		}
		if err := tx.Model(&model.FeatureRunItem{}).
			Where("last_purge_id = ? AND materialization_state = 'purging'", purgeID).
			Update("materialization_state", "available").Error; err != nil {
			return err
		}
		return d.createPurgeLifecycleEvents(tx, purgeID, "purge_fail", "purging", "failed")
	})
}

func (d *FeatureRunDao) createPurgeLifecycleEvents(
	tx *gorm.DB,
	purgeID, action, before, after string,
) error {
	return tx.Exec(`
		INSERT INTO govern.feature_lifecycle_event
		    (feature_id, feature_version_id, action,
		     before_status, after_status, manifest_checksum, details)
		SELECT DISTINCT version.feature_id, version.id, ?, ?, ?,
		       version.manifest_checksum,
		       jsonb_build_object('purge_id', ?::text)
		FROM govern.feature_data_purge_target AS target
		JOIN govern.feature_version AS version ON version.id = target.feature_version_id
		WHERE target.purge_id = ?::uuid`,
		action, before, after, purgeID, purgeID).Error
}
