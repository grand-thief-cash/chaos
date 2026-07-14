package dao

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"sort"
	"time"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type FeatureRunDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewFeatureRunDao(dsName string) *FeatureRunDao {
	return &FeatureRunDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_FEATURE_RUN),
		dsName:        dsName,
	}
}

func (d *FeatureRunDao) Start(ctx context.Context) error {
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

func (d *FeatureRunDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

func (d *FeatureRunDao) CreateOrReuse(ctx context.Context, run *model.FeatureRun, force bool) (*model.FeatureRun, bool, error) {
	var result *model.FeatureRun
	reused := false
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", run.RequestFingerprint).Error; err != nil {
			return err
		}
		var existing model.FeatureRun
		err := tx.Where("request_fingerprint = ? AND status IN ?", run.RequestFingerprint,
			[]string{"queued", "planning", "running", "validating", "succeeded"}).
			Order("created_at DESC").First(&existing).Error
		if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
			return err
		}
		if err == nil && !force {
			result = &existing
			reused = true
			return nil
		}
		if err == nil && force && run.RetryOfRunID == nil {
			run.RetryOfRunID = &existing.RunID
		}
		if err := tx.Create(run).Error; err != nil {
			return err
		}
		copy := *run
		result = &copy
		return nil
	})
	return result, reused, err
}

func (d *FeatureRunDao) GetRun(ctx context.Context, runID string) (*model.FeatureRun, error) {
	var run model.FeatureRun
	if err := d.db.WithContext(ctx).Where("run_id = ?", runID).First(&run).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorNotFound, "RUN_NOT_FOUND", "feature run %s was not found", runID)
		}
		return nil, err
	}
	return &run, nil
}

func (d *FeatureRunDao) GetRunDetail(ctx context.Context, runID string, includeSubjects bool) (*model.FeatureRunDetail, error) {
	run, err := d.GetRun(ctx, runID)
	if err != nil {
		return nil, err
	}
	var items []model.FeatureRunItem
	if err := d.db.WithContext(ctx).Where("run_id = ?", runID).Order("feature_version_id ASC").Find(&items).Error; err != nil {
		return nil, err
	}
	detail := &model.FeatureRunDetail{Run: *run, Items: items}
	if includeSubjects {
		if err := d.db.WithContext(ctx).Where("run_id = ?", runID).Order("security_id ASC").Find(&detail.Subjects).Error; err != nil {
			return nil, err
		}
	}
	return detail, nil
}

func (d *FeatureRunDao) ListRuns(ctx context.Context, f model.FeatureRunFilters, limit, offset int) ([]model.FeatureRun, int64, error) {
	q := d.db.WithContext(ctx).Model(&model.FeatureRun{})
	if f.Status != "" {
		q = q.Where("govern.feature_run.status = ?", f.Status)
	}
	if f.ProducerService != "" {
		q = q.Where("govern.feature_run.producer_service = ?", f.ProducerService)
	}
	if f.BackfillID != "" {
		q = q.Where("govern.feature_run.backfill_id = ?", f.BackfillID)
	}
	if f.FeatureVersionID != 0 {
		q = q.Joins("JOIN govern.feature_run_item ON feature_run_item.run_id = govern.feature_run.run_id").
			Where("feature_run_item.feature_version_id = ?", f.FeatureVersionID)
	}
	var total int64
	if err := q.Distinct("govern.feature_run.run_id").Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []model.FeatureRun
	q = q.Select("govern.feature_run.*").Distinct().Order("as_of_time DESC, created_at DESC")
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

func (d *FeatureRunDao) BatchSubjects(ctx context.Context, runID string, subjects []model.FeatureRunSubject) (int, error) {
	inserted := 0
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var existing []model.FeatureRunSubject
		if err := tx.Where("run_id = ?", runID).Find(&existing).Error; err != nil {
			return err
		}
		byID := make(map[uint64]model.FeatureRunSubject, len(existing))
		for _, row := range existing {
			byID[row.SecurityID] = row
		}
		pending := make([]model.FeatureRunSubject, 0, len(subjects))
		for _, row := range subjects {
			if old, ok := byID[row.SecurityID]; ok {
				if old.SymbolSnapshot != row.SymbolSnapshot || old.Exchange != row.Exchange || old.AssetType != row.AssetType || old.IncludedReason != row.IncludedReason {
					return model.NewFeatureError(model.FeatureErrorConflict, "RUN_SUBJECT_CONFLICT",
						"run %s already has a different snapshot for security_id %d", runID, row.SecurityID)
				}
				continue
			}
			pending = append(pending, row)
		}
		if len(pending) > 0 {
			if err := tx.CreateInBatches(pending, 500).Error; err != nil {
				return err
			}
			inserted = len(pending)
		}
		return nil
	})
	return inserted, err
}

func (d *FeatureRunDao) BatchItems(ctx context.Context, runID string, versionIDs []uint64) (int, error) {
	rows := make([]model.FeatureRunItem, 0, len(versionIDs))
	for _, id := range versionIDs {
		rows = append(rows, model.FeatureRunItem{
			RunID: runID, FeatureVersionID: id, Status: "queued",
			QualitySummary: model.NewJSONValue(map[string]any{}),
		})
	}
	res := d.db.WithContext(ctx).Clauses(clause.OnConflict{DoNothing: true}).CreateInBatches(rows, 200)
	return int(res.RowsAffected), res.Error
}

func (d *FeatureRunDao) GetRunItem(ctx context.Context, runID string, versionID uint64) (*model.FeatureRunItem, error) {
	var item model.FeatureRunItem
	if err := d.db.WithContext(ctx).Where("run_id = ? AND feature_version_id = ?", runID, versionID).First(&item).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, model.NewFeatureError(model.FeatureErrorNotFound, "RUN_ITEM_NOT_FOUND",
				"run item %s/%d was not found", runID, versionID)
		}
		return nil, err
	}
	return &item, nil
}

func (d *FeatureRunDao) UpdateRunStatus(ctx context.Context, runID, expected, next string, updates map[string]any) (*model.FeatureRun, error) {
	updates["status"] = next
	updates["updated_at"] = gorm.Expr("NOW()")
	if next == "running" {
		updates["started_at"] = gorm.Expr("COALESCE(started_at, NOW())")
	}
	if IsTerminalRunStatus(next) {
		updates["finished_at"] = gorm.Expr("NOW()")
	}
	res := d.db.WithContext(ctx).Model(&model.FeatureRun{}).
		Where("run_id = ? AND status = ?", runID, expected).Updates(updates)
	if res.Error != nil {
		return nil, res.Error
	}
	if res.RowsAffected != 1 {
		if _, err := d.GetRun(ctx, runID); err != nil {
			return nil, err
		}
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_STATE_CONFLICT",
			"run %s is not in expected status %s", runID, expected)
	}
	return d.GetRun(ctx, runID)
}

func (d *FeatureRunDao) UpdateItemStatus(ctx context.Context, runID string, versionID uint64, expected, next string, updates map[string]any) (*model.FeatureRunItem, error) {
	updates["status"] = next
	if next == "running" {
		updates["started_at"] = gorm.Expr("COALESCE(started_at, NOW())")
	}
	if IsTerminalItemStatus(next) {
		updates["finished_at"] = gorm.Expr("NOW()")
	}
	res := d.db.WithContext(ctx).Model(&model.FeatureRunItem{}).
		Where("run_id = ? AND feature_version_id = ? AND status = ?", runID, versionID, expected).
		Updates(updates)
	if res.Error != nil {
		return nil, res.Error
	}
	if res.RowsAffected != 1 {
		if _, err := d.GetRunItem(ctx, runID, versionID); err != nil {
			return nil, err
		}
		return nil, model.NewFeatureError(model.FeatureErrorConflict, "RUN_ITEM_STATE_CONFLICT",
			"run item %s/%d is not in expected status %s", runID, versionID, expected)
	}
	return d.GetRunItem(ctx, runID, versionID)
}

func (d *FeatureRunDao) SubjectIDSet(ctx context.Context, runID string) (map[uint64]struct{}, error) {
	var ids []uint64
	if err := d.db.WithContext(ctx).Model(&model.FeatureRunSubject{}).Where("run_id = ?", runID).Pluck("security_id", &ids).Error; err != nil {
		return nil, err
	}
	result := make(map[uint64]struct{}, len(ids))
	for _, id := range ids {
		result[id] = struct{}{}
	}
	return result, nil
}

func (d *FeatureRunDao) RunPreparationCounts(ctx context.Context, runID string) (subjects int64, items int64, err error) {
	if err = d.db.WithContext(ctx).Model(&model.FeatureRunSubject{}).Where("run_id = ?", runID).Count(&subjects).Error; err != nil {
		return 0, 0, err
	}
	if err = d.db.WithContext(ctx).Model(&model.FeatureRunItem{}).Where("run_id = ?", runID).Count(&items).Error; err != nil {
		return 0, 0, err
	}
	return subjects, items, nil
}

func (d *FeatureRunDao) WriteNumericValues(ctx context.Context, values []model.FeatureNumericValue) (int, error) {
	if len(values) == 0 {
		return 0, nil
	}
	inserted := 0
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		lockKey := fmt.Sprintf("%s/%d/%s", values[0].RunID, values[0].FeatureVersionID, values[0].ObservedAt.UTC().Format(time.RFC3339Nano))
		if err := tx.Exec("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", lockKey).Error; err != nil {
			return err
		}
		ids := make([]uint64, 0, len(values))
		for _, row := range values {
			ids = append(ids, row.SecurityID)
		}
		var existing []model.FeatureNumericValue
		if err := tx.Where("run_id = ? AND feature_version_id = ? AND observed_at = ? AND security_id IN ?",
			values[0].RunID, values[0].FeatureVersionID, values[0].ObservedAt, ids).Find(&existing).Error; err != nil {
			return err
		}
		byID := make(map[uint64]model.FeatureNumericValue, len(existing))
		for _, row := range existing {
			byID[row.SecurityID] = row
		}
		pending := make([]model.FeatureNumericValue, 0, len(values))
		for _, row := range values {
			if old, ok := byID[row.SecurityID]; ok {
				if !numericValuesEqual(old, row) {
					return model.NewFeatureError(model.FeatureErrorConflict, "VALUE_WRITE_CONFLICT",
						"numeric value already exists with different content for run=%s version=%d security_id=%d observed_at=%s",
						row.RunID, row.FeatureVersionID, row.SecurityID, row.ObservedAt.Format(time.RFC3339Nano))
				}
				continue
			}
			pending = append(pending, row)
		}
		if len(pending) > 0 {
			if err := tx.CreateInBatches(pending, 500).Error; err != nil {
				return err
			}
			inserted = len(pending)
		}
		return nil
	})
	return inserted, err
}

func numericValuesEqual(a, b model.FeatureNumericValue) bool {
	if a.ValueStatus != b.ValueStatus || !a.ObservedAt.Equal(b.ObservedAt) || !optionalTimeEqual(a.SourceMaxAvailableAt, b.SourceMaxAvailableAt) {
		return false
	}
	if (a.Value == nil) != (b.Value == nil) {
		return false
	}
	if a.Value != nil && math.Float64bits(*a.Value) != math.Float64bits(*b.Value) {
		return false
	}
	var left, right any
	if json.Unmarshal(a.QualityFlags, &left) != nil || json.Unmarshal(b.QualityFlags, &right) != nil {
		return false
	}
	leftJSON, _ := json.Marshal(left)
	rightJSON, _ := json.Marshal(right)
	return string(leftJSON) == string(rightJSON)
}

func optionalTimeEqual(a, b *time.Time) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return a.Equal(*b)
}

func IsTerminalRunStatus(status string) bool {
	switch status {
	case "succeeded", "partially_succeeded", "failed", "cancelled", "aborted":
		return true
	default:
		return false
	}
}

func IsTerminalItemStatus(status string) bool {
	switch status {
	case "succeeded", "failed", "skipped":
		return true
	default:
		return false
	}
}

func (d *FeatureRunDao) ListRunItems(ctx context.Context, runID string) ([]model.FeatureRunItem, error) {
	var rows []model.FeatureRunItem
	if err := d.db.WithContext(ctx).Where("run_id = ?", runID).Order("feature_version_id ASC").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (d *FeatureRunDao) QueryValues(ctx context.Context, q model.FeatureValueQuery) ([]model.FeatureNumericValue, int64, error) {
	db := d.db.WithContext(ctx).Table("dwd.feature_value_numeric AS fv").
		Joins("JOIN govern.feature_run r ON r.run_id = fv.run_id").
		Where("r.status = 'succeeded'")

	versionID := q.FeatureVersionID
	if versionID == 0 && q.FeatureCode != "" {
		versionQuery := d.db.WithContext(ctx).Table("govern.feature_version AS v").
			Select("v.id").Joins("JOIN govern.feature_definition d ON d.id = v.feature_id").
			Where("d.feature_code = ?", q.FeatureCode)
		if q.VersionNumber > 0 {
			versionQuery = versionQuery.Where("v.version_number = ?", q.VersionNumber)
		} else {
			versionQuery = versionQuery.Where("v.status = 'published'").
				Joins("JOIN govern.feature_run_item i ON i.feature_version_id = v.id AND i.status = 'succeeded'").
				Joins("JOIN govern.feature_run vr ON vr.run_id = i.run_id AND vr.status = 'succeeded'").
				Order("v.version_number DESC")
		}
		if err := versionQuery.Limit(1).Scan(&versionID).Error; err != nil {
			return nil, 0, err
		}
		if versionID == 0 {
			return []model.FeatureNumericValue{}, 0, nil
		}
	}
	if versionID != 0 {
		db = db.Where("fv.feature_version_id = ?", versionID)
	}
	if q.RunID != "" {
		db = db.Where("fv.run_id = ?", q.RunID)
	} else if q.Latest {
		var latestRunID string
		runQuery := d.db.WithContext(ctx).Table("govern.feature_run AS r").
			Select("r.run_id").Joins("JOIN govern.feature_run_item i ON i.run_id = r.run_id").
			Where("i.feature_version_id = ? AND i.status = 'succeeded' AND r.status = 'succeeded'", versionID).
			Order("r.as_of_time DESC, r.created_at DESC").Limit(1)
		if err := runQuery.Scan(&latestRunID).Error; err != nil {
			return nil, 0, err
		}
		if latestRunID == "" {
			return []model.FeatureNumericValue{}, 0, nil
		}
		db = db.Where("fv.run_id = ?", latestRunID)
	}
	if len(q.SecurityIDs) > 0 {
		db = db.Where("fv.security_id IN ?", q.SecurityIDs)
	}
	if q.ObservedFrom != nil {
		db = db.Where("fv.observed_at >= ?", *q.ObservedFrom)
	}
	if q.ObservedTo != nil {
		db = db.Where("fv.observed_at <= ?", *q.ObservedTo)
	}
	var total int64
	if err := db.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []model.FeatureNumericValue
	read := db.Select("fv.*").Order("fv.observed_at DESC, fv.security_id ASC")
	if q.Limit > 0 {
		read = read.Limit(q.Limit)
	}
	if q.Offset > 0 {
		read = read.Offset(q.Offset)
	}
	if err := read.Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (d *FeatureRunDao) CreateBackfill(ctx context.Context, job *model.FeatureBackfillJob, runs []model.FeatureRun) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(job).Error; err != nil {
			return err
		}
		if len(runs) > 0 {
			return tx.CreateInBatches(runs, 100).Error
		}
		return nil
	})
}

func (d *FeatureRunDao) GetBackfill(ctx context.Context, backfillID string) (*model.FeatureBackfillJob, []model.FeatureRun, error) {
	var job model.FeatureBackfillJob
	if err := d.db.WithContext(ctx).Where("backfill_id = ?", backfillID).First(&job).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil, model.NewFeatureError(model.FeatureErrorNotFound, "BACKFILL_NOT_FOUND", "backfill %s was not found", backfillID)
		}
		return nil, nil, err
	}
	var runs []model.FeatureRun
	if err := d.db.WithContext(ctx).Where("backfill_id = ?", backfillID).
		Order("backfill_sequence ASC, backfill_attempt ASC").Find(&runs).Error; err != nil {
		return nil, nil, err
	}
	return &job, runs, nil
}

func (d *FeatureRunDao) CreateBackfillRetries(ctx context.Context, backfillID string, retries []model.FeatureRun) ([]model.FeatureRun, error) {
	if len(retries) == 0 {
		return []model.FeatureRun{}, nil
	}
	inserted := make([]model.FeatureRun, 0, len(retries))
	err := d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", backfillID).Error; err != nil {
			return err
		}
		for i := range retries {
			retry := retries[i]
			var currentAttempt int
			if err := tx.Model(&model.FeatureRun{}).
				Where("backfill_id = ? AND as_of_time = ?", backfillID, retry.AsOfTime).
				Select("COALESCE(MAX(backfill_attempt), 0)").Scan(&currentAttempt).Error; err != nil {
				return err
			}
			if retry.BackfillAttempt == nil || currentAttempt >= *retry.BackfillAttempt {
				continue
			}
			if err := tx.Create(&retry).Error; err != nil {
				return err
			}
			inserted = append(inserted, retry)
		}
		return nil
	})
	return inserted, err
}

func (d *FeatureRunDao) SetBackfillCancelled(ctx context.Context, backfillID string) error {
	return d.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Model(&model.FeatureBackfillJob{}).Where("backfill_id = ? AND status NOT IN ?", backfillID,
			[]string{"succeeded", "failed", "cancelled"}).Updates(map[string]any{"status": "cancelled", "updated_at": gorm.Expr("NOW()")})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected == 0 {
			return model.NewFeatureError(model.FeatureErrorConflict, "BACKFILL_STATE_CONFLICT", "backfill %s cannot be cancelled", backfillID)
		}
		return tx.Model(&model.FeatureRun{}).
			Where("backfill_id = ? AND status = 'queued'", backfillID).
			Updates(map[string]any{"status": "cancelled", "finished_at": gorm.Expr("NOW()"), "updated_at": gorm.Expr("NOW()")}).Error
	})
}

func (d *FeatureRunDao) RefreshBackfillCounts(ctx context.Context, backfillID string) error {
	if backfillID == "" {
		return nil
	}
	type row struct {
		Status string
		Count  int
	}
	var rows []row
	err := d.db.WithContext(ctx).Raw(`
		WITH latest AS (
			SELECT DISTINCT ON (as_of_time) as_of_time, status
			FROM govern.feature_run
			WHERE backfill_id = ?
			ORDER BY as_of_time, backfill_attempt DESC
		)
		SELECT status, COUNT(*)::int AS count FROM latest GROUP BY status`, backfillID).Scan(&rows).Error
	if err != nil {
		return err
	}
	counts := make(map[string]int)
	for _, r := range rows {
		counts[r.Status] = r.Count
	}
	total := 0
	for _, count := range counts {
		total += count
	}
	succeeded := counts["succeeded"]
	failed := counts["failed"] + counts["aborted"]
	status := "running"
	if total > 0 && succeeded == total {
		status = "succeeded"
	} else if failed == total && total > 0 {
		status = "failed"
	} else if succeeded+failed == total && total > 0 {
		status = "partially_succeeded"
	} else if counts["queued"] == total {
		status = "queued"
	}
	return d.db.WithContext(ctx).Model(&model.FeatureBackfillJob{}).Where("backfill_id = ? AND status <> 'cancelled'", backfillID).
		Updates(map[string]any{
			"status": status, "total_count": total, "succeeded_count": succeeded,
			"failed_count": failed, "updated_at": gorm.Expr("NOW()"),
		}).Error
}

// LatestBackfillRuns returns only the highest attempt for each as_of time.
func LatestBackfillRuns(runs []model.FeatureRun) []model.FeatureRun {
	byTime := make(map[int64]model.FeatureRun)
	for _, run := range runs {
		key := run.AsOfTime.UnixNano()
		old, ok := byTime[key]
		if !ok || valueOrZero(run.BackfillAttempt) > valueOrZero(old.BackfillAttempt) {
			byTime[key] = run
		}
	}
	result := make([]model.FeatureRun, 0, len(byTime))
	for _, run := range byTime {
		result = append(result, run)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].AsOfTime.Before(result[j].AsOfTime) })
	return result
}

func valueOrZero(v *int) int {
	if v == nil {
		return 0
	}
	return *v
}
