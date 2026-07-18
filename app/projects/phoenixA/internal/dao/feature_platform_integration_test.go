package dao

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	_ "github.com/jackc/pgx/v5/stdlib"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

const featurePlatformTestDSNEnv = "PHOENIXA_POSTGRES_TEST_DSN"

func TestFeaturePlatformMigrationContract(t *testing.T) {
	migration := readFeaturePlatformMigration(t)
	for _, fragment := range []string{
		"CREATE TABLE IF NOT EXISTS govern.feature_definition",
		"CREATE TABLE IF NOT EXISTS govern.feature_version",
		"CREATE TABLE IF NOT EXISTS govern.feature_implementation",
		"CREATE TABLE IF NOT EXISTS govern.feature_dependency",
		"CREATE TABLE IF NOT EXISTS govern.feature_backfill_job",
		"CREATE TABLE IF NOT EXISTS govern.feature_run",
		"CREATE TABLE IF NOT EXISTS govern.feature_run_item",
		"CREATE TABLE IF NOT EXISTS govern.feature_run_subject",
		"CREATE TABLE IF NOT EXISTS dwd.feature_value_numeric",
		"TABLESPACE warm_storage",
		"create_hypertable(",
		"uk_feature_run_backfill_attempt",
		"trg_feature_value_numeric_data_cutoff",
		"trg_feature_value_numeric_immutable",
		"trg_feature_version_published_immutable",
	} {
		if !strings.Contains(migration, fragment) {
			t.Errorf("0008_feature_platform.sql is missing %q", fragment)
		}
	}
	recoveryPath := filepath.Join("..", "..", "migrations", "postgresql", "security", "0009_feature_platform_recovery.sql")
	recovery, err := os.ReadFile(recoveryPath)
	if err != nil {
		t.Fatalf("read recovery migration: %v", err)
	}
	if !strings.Contains(string(recovery), "idx_feature_run_stale_active") {
		t.Fatal("0009_feature_platform_recovery.sql is missing the active heartbeat index")
	}
}

// TestFeaturePlatformMigrationPostgres exercises the PostgreSQL-enforced
// immutability and PIT cutoff rules. CI can supply a disposable, fully migrated
// TimescaleDB through PHOENIXA_POSTGRES_TEST_DSN. All work is rolled back.
func TestFeaturePlatformMigrationPostgres(t *testing.T) {
	dsn := strings.TrimSpace(os.Getenv(featurePlatformTestDSNEnv))
	if dsn == "" {
		t.Skipf("set %s to run the Feature Platform PostgreSQL test", featurePlatformTestDSNEnv)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatalf("open PostgreSQL test database: %v", err)
	}
	defer db.Close()
	if err := db.PingContext(ctx); err != nil {
		t.Fatalf("ping PostgreSQL test database: %v", err)
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		t.Fatalf("begin transaction: %v", err)
	}
	defer func() { _ = tx.Rollback() }()

	// 0008 intentionally builds on the governed field dictionary from 0003.
	// Provision that prerequisite inside the same rollback-only transaction so
	// the contract test also works against a clean PhoenixA test database.
	governPath := filepath.Join("..", "..", "migrations", "postgresql", "security", "0003_govern.sql")
	governMigration, err := os.ReadFile(governPath)
	if err != nil {
		t.Fatalf("read prerequisite migration %s: %v", governPath, err)
	}
	if _, err := tx.ExecContext(ctx, string(governMigration)); err != nil {
		t.Fatalf("apply Feature Platform prerequisite migration: %v", err)
	}
	if _, err := tx.ExecContext(ctx, "CREATE SCHEMA IF NOT EXISTS dwd"); err != nil {
		t.Fatalf("ensure dwd schema: %v", err)
	}
	featureMigration := readFeaturePlatformMigration(t)
	var hasWarmStorage bool
	if err := tx.QueryRowContext(ctx, "SELECT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'warm_storage')").Scan(&hasWarmStorage); err != nil {
		t.Fatalf("inspect warm_storage tablespace: %v", err)
	}
	if !hasWarmStorage {
		// Physical tier placement is asserted by the static contract above. The
		// fallback keeps trigger/constraint validation runnable on developer DBs
		// where the DBA-managed tablespace has not been provisioned.
		featureMigration = strings.ReplaceAll(featureMigration, "TABLESPACE warm_storage", "TABLESPACE pg_default")
	}
	var hasTimescale bool
	if err := tx.QueryRowContext(ctx, "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable')").Scan(&hasTimescale); err != nil {
		t.Fatalf("inspect TimescaleDB functions: %v", err)
	}
	if !hasTimescale {
		hypertableDDL := `SELECT create_hypertable(
    'dwd.feature_value_numeric',
    'observed_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);`
		featureMigration = strings.Replace(featureMigration, hypertableDDL, "-- create_hypertable unavailable in this PostgreSQL test database", 1)
	}
	if _, err := tx.ExecContext(ctx, featureMigration); err != nil {
		t.Fatalf("apply Feature Platform migration: %v", err)
	}
	recoveryPath := filepath.Join("..", "..", "migrations", "postgresql", "security", "0009_feature_platform_recovery.sql")
	recoveryMigration, err := os.ReadFile(recoveryPath)
	if err != nil {
		t.Fatalf("read Feature Platform recovery migration: %v", err)
	}
	if _, err := tx.ExecContext(ctx, string(recoveryMigration)); err != nil {
		t.Fatalf("apply Feature Platform recovery migration: %v", err)
	}

	suffix := time.Now().UTC().Format("150405000000")
	featureCode := "test.feature.platform_" + suffix
	var featureID, versionID, implementationID int64
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_definition
		    (feature_code, display_name, description, kind, entity_type, value_type,
		     unit, category, owner, status, tags)
		VALUES ($1, 'Phase 1 fixture', '', 'metric', 'security', 'number', '', 'test',
		        'codex', 'draft', '[]'::jsonb)
		RETURNING id`, featureCode).Scan(&featureID)
	if err != nil {
		t.Fatalf("insert feature definition: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_version
		    (feature_id, version_number, status, frequency, as_of_semantics,
		     missing_policy, manifest_checksum, manifest_snapshot)
		VALUES ($1, 1, 'draft', 'on_demand', 'snapshot', 'explicit_missing', $2,
		        '{"fixture":true}'::jsonb)
		RETURNING id`, featureID, strings.Repeat("a", 64)).Scan(&versionID)
	if err != nil {
		t.Fatalf("insert feature version: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_implementation
		    (feature_version_id, kind, producer_service, backend, entrypoint,
		     implementation_revision, config, checksum, is_canonical, status)
		VALUES ($1, 'python', 'artemis', 'pandas', 'fixture', 1, '{}'::jsonb, $2, TRUE, 'active')
		RETURNING id`, versionID, strings.Repeat("b", 64)).Scan(&implementationID)
	if err != nil {
		t.Fatalf("insert feature implementation: %v", err)
	}
	upstreamCode := featureCode + ".upstream"
	grandparentCode := featureCode + ".grandparent"
	var upstreamFeatureID, upstreamVersionID, grandparentFeatureID, grandparentVersionID, dataFieldID int64
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_definition
		    (feature_code, display_name, description, kind, entity_type, value_type,
		     unit, category, owner, status, tags)
		VALUES ($1, 'Phase 3 upstream fixture', '', 'metric', 'security', 'number', '',
		        'test', 'codex', 'draft', '[]'::jsonb)
		RETURNING id`, upstreamCode).Scan(&upstreamFeatureID)
	if err != nil {
		t.Fatalf("insert upstream feature definition: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_version
		    (feature_id, version_number, status, frequency, as_of_semantics,
		     missing_policy, manifest_checksum, manifest_snapshot)
		VALUES ($1, 1, 'draft', 'on_demand', 'snapshot', 'explicit_missing', $2,
		        '{"fixture":"upstream"}'::jsonb)
		RETURNING id`, upstreamFeatureID, strings.Repeat("2", 64)).Scan(&upstreamVersionID)
	if err != nil {
		t.Fatalf("insert upstream feature version: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_definition
		    (feature_code, display_name, description, kind, entity_type, value_type,
		     unit, category, owner, status, tags)
		VALUES ($1, 'Phase 3 grandparent fixture', '', 'metric', 'security', 'number', '',
		        'test', 'codex', 'draft', '[]'::jsonb)
		RETURNING id`, grandparentCode).Scan(&grandparentFeatureID)
	if err != nil {
		t.Fatalf("insert grandparent feature definition: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.feature_version
		    (feature_id, version_number, status, frequency, as_of_semantics,
		     missing_policy, manifest_checksum, manifest_snapshot)
		VALUES ($1, 1, 'draft', 'on_demand', 'snapshot', 'explicit_missing', $2,
		        '{"fixture":"grandparent"}'::jsonb)
		RETURNING id`, grandparentFeatureID, strings.Repeat("3", 64)).Scan(&grandparentVersionID)
	if err != nil {
		t.Fatalf("insert grandparent feature version: %v", err)
	}
	err = tx.QueryRowContext(ctx, `
		INSERT INTO govern.data_field_dictionary
		    (contract_version, source, dataset, data_type, raw_field, canonical_field,
		     value_type, storage_location)
		VALUES ('phase3', 'fixture', 'feature_platform', 'probe', 'security_id',
		        'security_id', 'integer', 'top_level')
		RETURNING id`).Scan(&dataFieldID)
	if err != nil {
		t.Fatalf("insert lineage data field: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_dependency
		    (feature_version_id, dependency_kind, data_field_dictionary_id,
		     dependency_ref_snapshot, ordinal)
		VALUES ($1, 'data_field', $2, '{"fixture":"field"}'::jsonb, 0)`,
		grandparentVersionID, dataFieldID); err != nil {
		t.Fatalf("insert grandparent data-field dependency: %v", err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_version SET status = 'published', published_at = NOW() WHERE id = $1", grandparentVersionID); err != nil {
		t.Fatalf("publish grandparent feature version: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_dependency
		    (feature_version_id, dependency_kind, depends_on_feature_version_id,
		     dependency_ref_snapshot, ordinal)
		VALUES ($1, 'feature', $2, '{"fixture":"grandparent"}'::jsonb, 0)`,
		upstreamVersionID, grandparentVersionID); err != nil {
		t.Fatalf("insert upstream feature dependency: %v", err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_version SET status = 'published', published_at = NOW() WHERE id = $1", upstreamVersionID); err != nil {
		t.Fatalf("publish upstream feature version: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_dependency
		    (feature_version_id, dependency_kind, depends_on_feature_version_id,
		     dependency_ref_snapshot, ordinal)
		VALUES ($1, 'feature', $2, '{"fixture":"upstream"}'::jsonb, 0)`,
		versionID, upstreamVersionID); err != nil {
		t.Fatalf("insert root feature dependency: %v", err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_version SET status = 'published', published_at = NOW() WHERE id = $1", versionID); err != nil {
		t.Fatalf("publish feature version fixture: %v", err)
	}

	expectPostgresRejection(t, ctx, tx, "feature_version_immutable", "immutable",
		"UPDATE govern.feature_version SET manifest_checksum = $1 WHERE id = $2", strings.Repeat("c", 64), versionID)
	expectPostgresRejection(t, ctx, tx, "feature_child_immutable", "immutable",
		"UPDATE govern.feature_implementation SET config = '{\"changed\":true}'::jsonb WHERE id = $1", implementationID)

	runID := featureTestUUID(t)
	asOf := time.Date(2026, 7, 14, 8, 0, 0, 0, time.UTC)
	cutoff := asOf.Add(-time.Hour)
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_run
		    (run_id, request_fingerprint, producer_service, trigger_type, as_of_time,
		     data_cutoff_time, source_profile, market, universe_hash, request_payload,
		     code_revision, status)
		VALUES ($1, $2, 'artemis', 'api', $3, $4, 'test', 'zh_a', $5,
		        '{"root_feature_version_ids":[]}'::jsonb, 'fixture', 'running')`,
		runID, strings.Repeat("d", 64), asOf, cutoff, strings.Repeat("e", 64)); err != nil {
		t.Fatalf("insert feature run: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_run_item (run_id, feature_version_id, status)
		VALUES ($1, $2, 'running')`, runID, versionID); err != nil {
		t.Fatalf("insert run item: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_run_subject (run_id, security_id)
		VALUES ($1, 1)`, runID); err != nil {
		t.Fatalf("insert run subject: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO dwd.feature_value_numeric
		    (run_id, feature_version_id, security_id, observed_at, value, value_status,
		     quality_flags, source_max_available_at)
		VALUES ($1, $2, 1, $3, 1.0, 'valid', '{}'::jsonb, $4)`, runID, versionID, asOf, cutoff); err != nil {
		t.Fatalf("insert valid numeric value: %v", err)
	}

	gormTx, err := gorm.Open(postgres.New(postgres.Config{Conn: tx}), &gorm.Config{
		DisableAutomaticPing: true, SkipDefaultTransaction: true,
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		t.Fatalf("open GORM over integration transaction: %v", err)
	}
	runDao := &FeatureRunDao{db: gormTx}
	registryDao := &FeatureRegistryDao{db: gormTx}
	lineage, err := registryDao.GetLineage(ctx, featureCode)
	if err != nil {
		t.Fatalf("query recursive feature lineage: %v", err)
	}
	if len(lineage.Versions) != 1 || len(lineage.Versions[0].UpstreamFeatures) != 2 || len(lineage.Versions[0].UpstreamDataFields) != 1 {
		t.Fatalf("root lineage is incomplete: %#v", lineage)
	}
	grandparentLineage, err := registryDao.GetLineage(ctx, grandparentCode)
	if err != nil {
		t.Fatalf("query recursive downstream lineage: %v", err)
	}
	if len(grandparentLineage.Versions) != 1 || len(grandparentLineage.Versions[0].DownstreamFeatures) != 2 {
		t.Fatalf("grandparent downstream lineage is incomplete: %#v", grandparentLineage)
	}
	availability, err := registryDao.GetAvailability(ctx, featureCode, "test")
	if err != nil {
		t.Fatalf("query feature availability: %v", err)
	}
	if availability.SourceProfile != "test" || availability.DependencyStatus != "ready" ||
		availability.DataStatus != "ready" || availability.ImplementationStatus != "loadable" ||
		availability.MaterializationStatus != "running" || availability.ExecutionReadiness != "ready" {
		t.Fatalf("unexpected feature availability: %#v", availability)
	}
	latestQuery := model.FeatureValueQuery{FeatureCode: featureCode, Latest: true, Limit: 100}
	rows, total, err := runDao.QueryValues(ctx, latestQuery)
	if err != nil || total != 0 || len(rows) != 0 {
		t.Fatalf("running Run leaked through latest query: rows=%d total=%d err=%v", len(rows), total, err)
	}
	staleRunID := featureTestUUID(t)
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_run
		    (run_id, request_fingerprint, producer_service, trigger_type, as_of_time,
		     data_cutoff_time, source_profile, market, universe_hash, request_payload,
		     code_revision, status, heartbeat_at)
		VALUES ($1, $2, 'artemis', 'api', $3, $4, 'test', 'zh_a', $5,
		        '{"root_feature_version_ids":[]}'::jsonb, 'fixture', 'running', NOW() - INTERVAL '10 minutes')`,
		staleRunID, strings.Repeat("f", 64), asOf, cutoff, strings.Repeat("1", 64)); err != nil {
		t.Fatalf("insert stale run: %v", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO govern.feature_run_item (run_id, feature_version_id, status, quality_summary)
		VALUES ($1, $2, 'running', '{"status":"running"}'::jsonb)`, staleRunID, versionID); err != nil {
		t.Fatalf("insert stale run item: %v", err)
	}
	aborted, err := runDao.AbortStaleRuns(ctx, "artemis", time.Now().UTC().Add(-5*time.Minute))
	if err != nil || len(aborted) != 1 || aborted[0].RunID != staleRunID {
		t.Fatalf("abort stale runs = %#v, %v", aborted, err)
	}
	var staleStatus, itemStatus, itemError string
	var quality string
	if err := tx.QueryRowContext(ctx, "SELECT status FROM govern.feature_run WHERE run_id = $1", staleRunID).Scan(&staleStatus); err != nil {
		t.Fatalf("read stale run status: %v", err)
	}
	if err := tx.QueryRowContext(ctx, `
		SELECT status, error_code, quality_summary::text
		FROM govern.feature_run_item WHERE run_id = $1 AND feature_version_id = $2`, staleRunID, versionID).
		Scan(&itemStatus, &itemError, &quality); err != nil {
		t.Fatalf("read stale item status: %v", err)
	}
	if staleStatus != "aborted" || itemStatus != "failed" || itemError != "RUN_ABORTED_STALE" || !strings.Contains(quality, "gate_passed") {
		t.Fatalf("stale reconciliation split state: run=%s item=%s error=%s quality=%s", staleStatus, itemStatus, itemError, quality)
	}
	availability, err = registryDao.GetAvailability(ctx, featureCode, "test")
	if err != nil || availability.MaterializationStatus != "running" || availability.LatestSucceededRun != nil {
		t.Fatalf("active materialization availability after stale reconciliation = %#v, %v", availability, err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_run_item SET status = 'succeeded' WHERE run_id = $1", runID); err != nil {
		t.Fatalf("complete run item: %v", err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_run SET status = 'succeeded', finished_at = NOW() WHERE run_id = $1", runID); err != nil {
		t.Fatalf("complete run: %v", err)
	}
	availability, err = registryDao.GetAvailability(ctx, featureCode, "test")
	if err != nil || availability.MaterializationStatus != "succeeded" || availability.LatestSucceededRun == nil {
		t.Fatalf("succeeded materialization availability = %#v, %v", availability, err)
	}
	rows, total, err = runDao.QueryValues(ctx, latestQuery)
	if err != nil || total != 1 || len(rows) != 1 || rows[0].RunID != runID {
		t.Fatalf("succeeded latest query: rows=%#v total=%d err=%v", rows, total, err)
	}
	if _, err := tx.ExecContext(ctx, "UPDATE govern.feature_version SET status = 'deprecated', deprecated_at = NOW() WHERE id = $1", versionID); err != nil {
		t.Fatalf("deprecate feature version: %v", err)
	}
	rows, total, err = runDao.QueryValues(ctx, latestQuery)
	if err != nil || total != 0 || len(rows) != 0 {
		t.Fatalf("deprecated version participated in latest query: rows=%d total=%d err=%v", len(rows), total, err)
	}
	explicitQuery := model.FeatureValueQuery{FeatureCode: featureCode, VersionNumber: 1, Limit: 100}
	rows, total, err = runDao.QueryValues(ctx, explicitQuery)
	if err != nil || total != 1 || len(rows) != 1 {
		t.Fatalf("deprecated explicit version lost history: rows=%#v total=%d err=%v", rows, total, err)
	}

	expectPostgresRejection(t, ctx, tx, "feature_value_cutoff", "exceeds data_cutoff_time", `
		INSERT INTO dwd.feature_value_numeric
		    (run_id, feature_version_id, security_id, observed_at, value, value_status,
		     quality_flags, source_max_available_at)
		VALUES ($1, $2, 2, $3, 2.0, 'valid', '{}'::jsonb, $4)`, runID, versionID, asOf, asOf)
	expectPostgresRejection(t, ctx, tx, "feature_value_update", "immutable",
		"UPDATE dwd.feature_value_numeric SET value = 2.0 WHERE run_id = $1", runID)
	expectPostgresRejection(t, ctx, tx, "feature_value_delete", "immutable",
		"DELETE FROM dwd.feature_value_numeric WHERE run_id = $1", runID)
}

func readFeaturePlatformMigration(t *testing.T) string {
	t.Helper()
	path := filepath.Join("..", "..", "migrations", "postgresql", "security", "0008_feature_platform.sql")
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read migration %s: %v", path, err)
	}
	return string(content)
}

func featureTestUUID(t *testing.T) string {
	t.Helper()
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		t.Fatalf("generate UUID: %v", err)
	}
	raw[6] = (raw[6] & 0x0f) | 0x40
	raw[8] = (raw[8] & 0x3f) | 0x80
	return fmt.Sprintf("%s-%s-%s-%s-%s",
		hex.EncodeToString(raw[0:4]), hex.EncodeToString(raw[4:6]), hex.EncodeToString(raw[6:8]),
		hex.EncodeToString(raw[8:10]), hex.EncodeToString(raw[10:16]))
}
