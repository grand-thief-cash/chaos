package dao

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

const securityIdentityTestDSNEnv = "PHOENIXA_POSTGRES_TEST_DSN"

// TestSecurityIdentityMigrationPostgres exercises the database-enforced part
// of the permanent security_id contract. CI supplies a disposable PostgreSQL
// database through PHOENIXA_POSTGRES_TEST_DSN. Every DDL and DML statement is
// executed in one transaction and rolled back, so the test leaves no changes.
func TestSecurityIdentityMigrationPostgres(t *testing.T) {
	dsn := strings.TrimSpace(os.Getenv(securityIdentityTestDSNEnv))
	if dsn == "" {
		t.Skipf("set %s to run the PostgreSQL identity-gate test", securityIdentityTestDSNEnv)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
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

	migrationPath := filepath.Join("..", "..", "migrations", "postgresql", "security", "0007_security_identity_stability.sql")
	migration, err := os.ReadFile(migrationPath)
	if err != nil {
		t.Fatalf("read migration %s: %v", migrationPath, err)
	}
	if _, err := tx.ExecContext(ctx, string(migration)); err != nil {
		t.Fatalf("apply security identity migration: %v", err)
	}

	suffix := time.Now().UTC().Format("150405000000")
	symbol := "T" + suffix
	var originalID int64
	err = tx.QueryRowContext(ctx, `
		INSERT INTO ods.security_registry
		    (exchange, asset_type, symbol, market, name, status)
		VALUES ('SZ', 'stock', $1, 'zh_a', 'identity gate fixture', 'active')
		RETURNING id`, symbol).Scan(&originalID)
	if err != nil {
		t.Fatalf("insert security fixture: %v", err)
	}

	var upsertedID int64
	err = tx.QueryRowContext(ctx, `
		INSERT INTO ods.security_registry
		    (exchange, asset_type, symbol, market, name, status)
		VALUES ('SZ', 'stock', $1, 'zh_a', 'identity gate fixture updated', 'active')
		ON CONFLICT (exchange, asset_type, symbol) DO UPDATE
		SET name = EXCLUDED.name, updated_at = NOW()
		RETURNING id`, symbol).Scan(&upsertedID)
	if err != nil {
		t.Fatalf("natural-key upsert: %v", err)
	}
	if upsertedID != originalID {
		t.Fatalf("natural-key upsert changed security_id: first=%d second=%d", originalID, upsertedID)
	}

	expectPostgresRejection(t, ctx, tx, "natural_key_update", "immutable",
		"UPDATE ods.security_registry SET symbol = $1 WHERE id = $2", symbol+"X", originalID)
	expectPostgresRejection(t, ctx, tx, "delete", "permanent",
		"DELETE FROM ods.security_registry WHERE id = $1", originalID)
	expectPostgresRejection(t, ctx, tx, "truncate", "permanent",
		"TRUNCATE TABLE ods.security_registry")
}

func expectPostgresRejection(
	t *testing.T,
	ctx context.Context,
	tx *sql.Tx,
	savepoint string,
	wantMessage string,
	query string,
	args ...any,
) {
	t.Helper()
	if _, err := tx.ExecContext(ctx, "SAVEPOINT "+savepoint); err != nil {
		t.Fatalf("create savepoint %s: %v", savepoint, err)
	}

	_, gotErr := tx.ExecContext(ctx, query, args...)
	if gotErr == nil {
		t.Fatalf("expected PostgreSQL to reject %s", savepoint)
	}
	if !strings.Contains(strings.ToLower(gotErr.Error()), strings.ToLower(wantMessage)) {
		t.Errorf("%s rejection = %q, want message containing %q", savepoint, gotErr, wantMessage)
	}

	if _, err := tx.ExecContext(ctx, "ROLLBACK TO SAVEPOINT "+savepoint); err != nil {
		t.Fatalf("rollback savepoint %s after %v: %v", savepoint, gotErr, err)
	}
	if _, err := tx.ExecContext(ctx, "RELEASE SAVEPOINT "+savepoint); err != nil {
		t.Fatalf("release savepoint %s: %v", savepoint, err)
	}
}
