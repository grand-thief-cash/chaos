// Package migration provides a shared, version-tracked SQL migration runner
// for both MySQL GORM and PostgreSQL GORM components.
//
// Design:
//   - Each datasource maintains a `_migrations` tracking table (auto-created).
//   - Migration files must follow the naming convention: `NNNN_description.sql`
//     (e.g., `0001_init.sql`, `0002_add_index.sql`).
//   - Files are sorted lexically and executed in order.
//   - Already-applied migrations (tracked by filename) are skipped.
//   - PostgreSQL `$$` dollar-quoting is handled correctly.
//   - Each migration file runs inside a transaction (if supported).
//   - The component logs each migration applied.
package migration

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Dialect indicates the SQL dialect for minor syntax differences.
type Dialect string

const (
	DialectMySQL    Dialect = "mysql"
	DialectPostgres Dialect = "postgres"
)

// ResolveMigrateDir builds the canonical migration directory path from a base
// directory, dialect, and datasource name.
//
// Convention:
//
//	{base}/{dialect}/{datasource}/
//
// Example:
//
//	ResolveMigrateDir("./migrations", DialectPostgres, "kg")
//	→ "migrations/postgresql/kg"
//
//	ResolveMigrateDir("./migrations", DialectMySQL, "security")
//	→ "migrations/mysql/security"
func ResolveMigrateDir(base string, dialect Dialect, datasource string) string {
	return filepath.Join(base, dialectDirName(dialect), datasource)
}

// dialectDirName maps a Dialect to the canonical sub-directory name.
func dialectDirName(d Dialect) string {
	switch d {
	case DialectMySQL:
		return "mysql"
	case DialectPostgres:
		return "postgresql"
	default:
		return string(d)
	}
}

// Result holds statistics from a migration run.
type Result struct {
	Applied []string      // filenames of newly applied migrations
	Skipped []string      // filenames already applied (skipped)
	Elapsed time.Duration // total wall time
}

// Run executes pending migrations from dir against db.
//
// It will:
//  1. Create the `_migrations` tracking table if it doesn't exist.
//  2. Read all *.sql files from dir (non-recursive), sorted lexically.
//  3. Skip files that are already recorded in `_migrations`.
//  4. Execute each pending file's SQL statements.
//  5. Record success in `_migrations`.
//
// schema is optional (PostgreSQL only): if non-empty, the tracking table is
// created as `<firstSchema>._migrations` (first schema of a comma-separated
// list) and search_path is set to the full schema list before each migration
// file executes.
func Run(ctx context.Context, db *sql.DB, dialect Dialect, dir string, schema string) (*Result, error) {
	start := time.Now()
	res := &Result{}

	if strings.TrimSpace(dir) == "" {
		return res, fmt.Errorf("migration dir is empty")
	}

	// Ensure tracking table exists
	if err := ensureTrackingTable(ctx, db, dialect, schema); err != nil {
		return res, fmt.Errorf("create migration tracking table: %w", err)
	}

	// List applied migrations
	applied, err := listApplied(ctx, db, schema)
	if err != nil {
		return res, fmt.Errorf("list applied migrations: %w", err)
	}

	// List migration files
	files, err := listMigrationFiles(dir)
	if err != nil {
		return res, fmt.Errorf("list migration files: %w", err)
	}

	for _, f := range files {
		name := filepath.Base(f)
		if applied[name] {
			res.Skipped = append(res.Skipped, name)
			continue
		}

		if err := executeMigrationFile(ctx, db, dialect, f, schema); err != nil {
			return res, fmt.Errorf("migration %s failed: %w", name, err)
		}

		if err := recordApplied(ctx, db, name, schema); err != nil {
			return res, fmt.Errorf("record migration %s: %w", name, err)
		}

		res.Applied = append(res.Applied, name)
	}

	res.Elapsed = time.Since(start)
	return res, nil
}

// firstSchema returns the first schema of a comma-separated schema list
// (e.g. "ods,dwd,govern" -> "ods"). Used to qualify the _migrations tracking
// table, which can only live in a single schema. Returns "" when schema is empty.
func firstSchema(schema string) string {
	schema = strings.TrimSpace(schema)
	if schema == "" {
		return ""
	}
	return strings.TrimSpace(strings.Split(schema, ",")[0])
}

// trackingTableName returns the schema-qualified _migrations table name, using
// only the first schema when given a comma-separated list.
func trackingTableName(schema string) string {
	if s := firstSchema(schema); s != "" {
		return s + "._migrations"
	}
	return "_migrations"
}

// ensureTrackingTable creates the _migrations table if it doesn't exist.
func ensureTrackingTable(ctx context.Context, db *sql.DB, dialect Dialect, schema string) error {
	tableName := trackingTableName(schema)

	var ddl string
	switch dialect {
	case DialectMySQL:
		ddl = fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s (
			id         INT AUTO_INCREMENT PRIMARY KEY,
			filename   VARCHAR(512) NOT NULL UNIQUE,
			applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			checksum   VARCHAR(64) DEFAULT ''
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`, tableName)
	case DialectPostgres:
		ddl = fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s (
			id         BIGSERIAL PRIMARY KEY,
			filename   VARCHAR(512) NOT NULL UNIQUE,
			applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
			checksum   VARCHAR(64) DEFAULT ''
		)`, tableName)
	default:
		return fmt.Errorf("unsupported dialect: %s", dialect)
	}

	_, err := db.ExecContext(ctx, ddl)
	return err
}

// listApplied returns a set of already-applied migration filenames.
func listApplied(ctx context.Context, db *sql.DB, schema string) (map[string]bool, error) {
	tableName := trackingTableName(schema)

	rows, err := db.QueryContext(ctx, fmt.Sprintf("SELECT filename FROM %s ORDER BY filename", tableName))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	applied := make(map[string]bool)
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		applied[name] = true
	}
	return applied, rows.Err()
}

// recordApplied inserts a record into the tracking table.
func recordApplied(ctx context.Context, db *sql.DB, filename string, schema string) error {
	tableName := trackingTableName(schema)

	_, err := db.ExecContext(ctx,
		fmt.Sprintf("INSERT INTO %s (filename) VALUES ($1)", tableName),
		filename,
	)
	if err != nil {
		// MySQL uses ? placeholder
		_, err = db.ExecContext(ctx,
			fmt.Sprintf("INSERT INTO %s (filename) VALUES (?)", tableName),
			filename,
		)
	}
	return err
}

// listMigrationFiles returns sorted .sql file paths from dir.
func listMigrationFiles(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("read dir %s: %w", dir, err)
	}
	var files []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if strings.HasSuffix(strings.ToLower(e.Name()), ".sql") {
			files = append(files, filepath.Join(dir, e.Name()))
		}
	}
	sort.Strings(files)
	return files, nil
}

// executeMigrationFile reads and executes all statements in a single .sql file.
// For PostgreSQL, when schema is non-empty, search_path is set inside the
// transaction so bare-name DDL resolves to the configured schema(s). The schema
// string may be comma-separated (e.g. "ods,dwd,govern,kg,public"); SET
// search_path accepts a comma-separated list.
func executeMigrationFile(ctx context.Context, db *sql.DB, dialect Dialect, path string, schema string) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}

	content := string(b)
	var stmts []string
	switch dialect {
	case DialectPostgres:
		stmts = SplitPostgresStatements(content)
	default:
		stmts = splitSimple(content)
	}

	// Try to run in a transaction
	tx, txErr := db.BeginTx(ctx, nil)
	if txErr != nil {
		// If transaction not supported, run without. SET search_path is skipped
		// here to avoid the connection-pool pitfall (SET only applies to the
		// borrowed connection, not subsequent borrows). PostgreSQL always
		// supports transactions, so this branch is effectively unreachable for PG.
		for _, s := range stmts {
			if strings.TrimSpace(s) == "" {
				continue
			}
			if _, err := db.ExecContext(ctx, s); err != nil {
				return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
			}
		}
		return nil
	}

	// Set search_path IN TRANSACTION (same connection as the statements).
	if dialect == DialectPostgres && strings.TrimSpace(schema) != "" {
		if _, err := tx.ExecContext(ctx, fmt.Sprintf("SET search_path TO %s", schema)); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("set search_path for migration %s: %w", filepath.Base(path), err)
		}
	}

	for _, s := range stmts {
		if strings.TrimSpace(s) == "" {
			continue
		}
		if _, err := tx.ExecContext(ctx, s); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
		}
	}
	return tx.Commit()
}

// SplitPostgresStatements splits SQL by semicolons while respecting
// $$ dollar-quoting, single-quoted strings (” escaped), and -- line comments.
func SplitPostgresStatements(text string) []string {
	var stmts []string
	var current strings.Builder
	inDollar := false
	inQuote := false
	inLineComment := false

	for i := 0; i < len(text); i++ {
		// -- line comment: skip everything until newline
		if !inDollar && !inQuote && !inLineComment &&
			text[i] == '-' && i+1 < len(text) && text[i+1] == '-' {
			inLineComment = true
			current.WriteByte(text[i])
			current.WriteByte(text[i+1])
			i++
			continue
		}
		if inLineComment {
			current.WriteByte(text[i])
			if text[i] == '\n' {
				inLineComment = false
			}
			continue
		}
		// $$ dollar-quoting
		if !inQuote && text[i] == '$' && i+1 < len(text) && text[i+1] == '$' {
			inDollar = !inDollar
			current.WriteByte(text[i])
			current.WriteByte(text[i+1])
			i++
			continue
		}
		// single-quoted string with '' escape
		if !inDollar && text[i] == '\'' {
			if inQuote && i+1 < len(text) && text[i+1] == '\'' {
				current.WriteByte(text[i])
				current.WriteByte(text[i+1])
				i++
				continue
			}
			inQuote = !inQuote
			current.WriteByte(text[i])
			continue
		}
		// semicolon splits only outside quotes/comments
		if text[i] == ';' && !inDollar && !inQuote && !inLineComment {
			stmts = append(stmts, current.String())
			current.Reset()
			continue
		}
		current.WriteByte(text[i])
	}
	if current.Len() > 0 {
		stmts = append(stmts, current.String())
	}
	return stmts
}

// splitSimple splits SQL by semicolons (MySQL / simple SQL).
func splitSimple(text string) []string {
	return strings.Split(text, ";")
}
