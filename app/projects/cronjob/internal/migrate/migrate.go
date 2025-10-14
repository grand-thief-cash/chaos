package migrate

import (
	"context"
	"database/sql"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Run executes all .sql files in the given directory (non-recursive) in lexical order.
// A very lightweight migration runner for early phases; idempotency should
// be handled inside SQL (using IF NOT EXISTS, etc.).
func Run(ctx context.Context, db *sql.DB, dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("read migrations dir: %w", err)
	}
	var files []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.HasSuffix(name, ".sql") {
			files = append(files, filepath.Join(dir, name))
		}
	}
	sort.Strings(files)
	for _, f := range files {
		b, err := ioutil.ReadFile(f)
		if err != nil {
			return fmt.Errorf("read %s: %w", f, err)
		}
		// split on ; but keep simple (won't handle procedures); if complexity grows, switch to goose or migrate tool
		stmts := splitSQL(string(b))
		for _, s := range stmts {
			if strings.TrimSpace(s) == "" {
				continue
			}
			if _, err := db.ExecContext(ctx, s); err != nil {
				return fmt.Errorf("exec %s failed: %w", f, err)
			}
		}
	}
	return nil
}

func splitSQL(content string) []string {
	parts := strings.Split(content, ";")
	return parts
}
