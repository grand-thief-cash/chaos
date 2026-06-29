package dao

import (
	"context"
	"fmt"
	"regexp"
	"strings"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
)

// FieldCoverageDao persists data_field_coverage_observation rows and runs
// the scan that compares observed data_json keys against the governed set.
type FieldCoverageDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewFieldCoverageDao(dsName string) *FieldCoverageDao {
	return &FieldCoverageDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_FIELD_COVERAGE),
		dsName:        dsName,
	}
}

func (d *FieldCoverageDao) Start(ctx context.Context) error {
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

func (d *FieldCoverageDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// safeTableRe guards table-name interpolation. We only ever scan governed
// tables sourced from the dataset dictionary, so the input is trusted — but
// defense in depth.
var safeTableRe = regexp.MustCompile(`^[a-z_][a-z0-9_]{0,62}$`)

// ScanDataset scans `storageTable` (filtered by source) for distinct keys in
// data_json, classifies each against `governedKeys`, and upserts observations.
// `governedKeys` must be the raw_field set where storage_location='data_json'.
// Returns a summary with counts and the ungoverned key list.
//
// The scan samples at most `sampleLimit` rows (most recent by id). Pass 0 for
// no limit — appropriate for small tables but slow on multi-million-row ones.
func (d *FieldCoverageDao) ScanDataset(
	ctx context.Context,
	dataset, source, storageTable string,
	governedKeys map[string]bool,
	sampleLimit int,
) (*model.FieldCoverageScanResult, error) {
	if !safeTableRe.MatchString(storageTable) {
		return nil, fmt.Errorf("invalid storage_table name: %q", storageTable)
	}

	// 1. Aggregate distinct keys + counts from the table. We use a lateral
	//    join against jsonb_object_keys. sampleLimit caps work on big tables.
	//    We filter to jsonb_typeof = 'object' to skip any rows that predate
	//    the CHECK constraint and have a scalar/array data_json.
	keySQL := fmt.Sprintf(`
		SELECT key, COUNT(*) AS cnt
		FROM (
			SELECT data_json
			FROM %s
			WHERE source = ? AND jsonb_typeof(data_json) = 'object'
			ORDER BY id DESC
			%s
		) sub,
		LATERAL jsonb_object_keys(sub.data_json) AS key
		GROUP BY key
	`, storageTable, limitClause(sampleLimit))

	type keyRow struct {
		Key string `gorm:"column:key"`
		Cnt int64  `gorm:"column:cnt"`
	}
	var keys []keyRow
	if err := d.db.WithContext(ctx).Raw(keySQL, source).Scan(&keys).Error; err != nil {
		return nil, fmt.Errorf("scan keys from %s: %w", storageTable, err)
	}

	// 2. Determine rows scanned (for the summary).
	var rowsScanned int64
	countSQL := fmt.Sprintf(`SELECT COUNT(*) FROM %s WHERE source = ?`, storageTable)
	if sampleLimit > 0 {
		countSQL = fmt.Sprintf(`
			SELECT COUNT(*) FROM (
				SELECT 1 FROM %s WHERE source = ? ORDER BY id DESC LIMIT %d
			) t
		`, storageTable, sampleLimit)
	}
	if err := d.db.WithContext(ctx).Raw(countSQL, source).Scan(&rowsScanned).Error; err != nil {
		return nil, fmt.Errorf("count rows: %w", err)
	}

	result := &model.FieldCoverageScanResult{
		Dataset:      dataset,
		Source:       source,
		StorageTable: storageTable,
		RowsScanned:  rowsScanned,
		DistinctKeys: int64(len(keys)),
	}
	if len(keys) == 0 {
		return result, nil
	}

	// 3. Upsert observations in a single batch.
	placeholders := make([]string, 0, len(keys))
	args := make([]any, 0, len(keys)*6)
	for _, k := range keys {
		status := "ungoverned"
		if governedKeys[k.Key] {
			status = "governed"
		} else {
			result.UngovernedCount++
			result.UngovernedKeys = append(result.UngovernedKeys, k.Key)
		}
		placeholders = append(placeholders, "(?, ?, ?, ?, ?, ?, NOW(), NOW())")
		args = append(args, dataset, source, storageTable, k.Key, status, k.Cnt)
	}
	upsertSQL := fmt.Sprintf(`
		INSERT INTO govern.data_field_coverage_observation
		    (dataset, source, storage_table, observed_key, status, sample_count, first_seen_at, last_seen_at)
		VALUES %s
		ON CONFLICT (dataset, source, observed_key) DO UPDATE SET
		    status       = EXCLUDED.status,
		    sample_count = EXCLUDED.sample_count,
		    last_seen_at = NOW()
	`, strings.Join(placeholders, ", "))
	if err := d.db.WithContext(ctx).Exec(upsertSQL, args...).Error; err != nil {
		return nil, fmt.Errorf("upsert observations: %w", err)
	}

	result.GovernedCount = result.DistinctKeys - result.UngovernedCount
	return result, nil
}

func limitClause(n int) string {
	if n > 0 {
		return fmt.Sprintf("LIMIT %d", n)
	}
	return ""
}

// ListObservations returns observations optionally filtered by dataset and
// status. Sorted with ungoverned first, then by observed_key.
func (d *FieldCoverageDao) ListObservations(ctx context.Context, dataset, source, status string) ([]model.FieldCoverageObservation, error) {
	q := d.db.WithContext(ctx).Table("govern.data_field_coverage_observation")
	if dataset != "" {
		q = q.Where("dataset = ?", dataset)
	}
	if source != "" {
		q = q.Where("source = ?", source)
	}
	if status != "" {
		q = q.Where("status = ?", status)
	}
	q = q.Order("CASE status WHEN 'ungoverned' THEN 0 ELSE 1 END, observed_key ASC")
	var rows []model.FieldCoverageObservation
	if err := q.Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}
