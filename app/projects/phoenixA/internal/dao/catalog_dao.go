package dao

import (
	"context"
	"fmt"
	"regexp"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
)

// safeIdentifier validates that a SQL identifier contains only safe characters.
var SafeIdentifierRe = regexp.MustCompile(`^[a-zA-Z_][a-zA-Z0-9_]*$`)

// CatalogDao queries PostgreSQL system catalogs for metadata.
type CatalogDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewCatalogDao(dsName string) *CatalogDao {
	return &CatalogDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_CATALOG),
		dsName:        dsName,
	}
}

func (d *CatalogDao) Start(ctx context.Context) error {
	if err := d.BaseComponent.Start(ctx); err != nil {
		return err
	}
	db, err := d.GormComp.GetDB(d.dsName)
	if err != nil {
		return fmt.Errorf("get gorm db %s: %w", d.dsName, err)
	}
	d.db = db
	return nil
}

func (d *CatalogDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// DB returns the underlying gorm.DB for use by service layer queries.
func (d *CatalogDao) DB() *gorm.DB { return d.db }

// rawTableRow is the scan target for the table listing query.
type rawTableRow struct {
	SchemaName   string
	TableName    string
	RowEstimate  int64
	TotalBytes   int64
	TableBytes   int64
	IndexBytes   int64
	Tablespace   string
	ColumnCount  int
	HasJSONB     bool
	IsHypertable bool
}

// AnalyzeSchemas runs VACUUM ANALYZE on all tables in the given schemas to refresh pg statistics.
// VACUUM/ANALYZE cannot run inside a transaction, so we use a raw SQL connection.
func (d *CatalogDao) AnalyzeSchemas(ctx context.Context, schemas []string) {
	sqlDB, err := d.db.DB()
	if err != nil {
		return
	}
	for _, s := range schemas {
		if !SafeIdentifierRe.MatchString(s) {
			continue
		}
		conn, err := sqlDB.Conn(ctx)
		if err != nil {
			continue
		}
		_, _ = conn.ExecContext(ctx, fmt.Sprintf("VACUUM ANALYZE %s", s))
		conn.Close()
	}
}

// ListTables queries pg system catalogs for all user tables in the given schemas.
func (d *CatalogDao) ListTables(ctx context.Context, schemas []string) ([]rawTableRow, error) {
	if len(schemas) == 0 {
		schemas = []string{"public", "kg", "ods", "dwd", "govern"}
	}

	query := `
		SELECT
			n.nspname                                    AS schema_name,
			c.relname                                    AS table_name,
			COALESCE(s.n_live_tup, 0)                    AS row_estimate,
			COALESCE(pg_total_relation_size(c.oid), 0)   AS total_bytes,
			COALESCE(pg_relation_size(c.oid), 0)         AS table_bytes,
			COALESCE(pg_indexes_size(c.oid), 0)          AS index_bytes,
			COALESCE(ts.spcname, 'pg_default')           AS tablespace,
			(SELECT count(*) FROM information_schema.columns ic
			 WHERE ic.table_schema = n.nspname AND ic.table_name = c.relname) AS column_count,
			EXISTS (
				SELECT 1 FROM information_schema.columns ic
				WHERE ic.table_schema = n.nspname
				  AND ic.table_name = c.relname
				  AND ic.udt_name IN ('jsonb', 'json')
			) AS has_jsonb,
			EXISTS (
				SELECT 1 FROM information_schema.tables it
				WHERE it.table_schema = '_timescaledb_internal'
				  AND it.table_type = 'BASE TABLE'
			) AND EXISTS (
				SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'timescaledb'
			) AND EXISTS (
				SELECT 1 FROM _timescaledb_catalog.hypertable h
				WHERE h.schema_name = n.nspname AND h.table_name = c.relname
			) AS is_hypertable
		FROM pg_class c
		JOIN pg_namespace n ON n.oid = c.relnamespace
		LEFT JOIN pg_stat_user_tables s ON s.schemaname = n.nspname AND s.relname = c.relname
		LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace
		WHERE c.relkind = 'r'
		  AND n.nspname = ANY($1)
		ORDER BY total_bytes DESC
	`

	var rows []rawTableRow
	result := d.db.WithContext(ctx).Raw(query, schemas).Scan(&rows)
	if result.Error != nil {
		// If TimescaleDB is not installed, the query may fail on _timescaledb_catalog.
		// Retry without hypertable check.
		return d.listTablesSimple(ctx, schemas)
	}
	return rows, nil
}

// listTablesSimple is a fallback when TimescaleDB is not installed.
func (d *CatalogDao) listTablesSimple(ctx context.Context, schemas []string) ([]rawTableRow, error) {
	query := `
		SELECT
			n.nspname                                    AS schema_name,
			c.relname                                    AS table_name,
			COALESCE(s.n_live_tup, 0)                    AS row_estimate,
			COALESCE(pg_total_relation_size(c.oid), 0)   AS total_bytes,
			COALESCE(pg_relation_size(c.oid), 0)         AS table_bytes,
			COALESCE(pg_indexes_size(c.oid), 0)          AS index_bytes,
			COALESCE(ts.spcname, 'pg_default')           AS tablespace,
			(SELECT count(*) FROM information_schema.columns ic
			 WHERE ic.table_schema = n.nspname AND ic.table_name = c.relname) AS column_count,
			EXISTS (
				SELECT 1 FROM information_schema.columns ic
				WHERE ic.table_schema = n.nspname
				  AND ic.table_name = c.relname
				  AND ic.udt_name IN ('jsonb', 'json')
			) AS has_jsonb,
			false AS is_hypertable
		FROM pg_class c
		JOIN pg_namespace n ON n.oid = c.relnamespace
		LEFT JOIN pg_stat_user_tables s ON s.schemaname = n.nspname AND s.relname = c.relname
		LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace
		WHERE c.relkind = 'r'
		  AND n.nspname = ANY($1)
		ORDER BY total_bytes DESC
	`

	var rows []rawTableRow
	if err := d.db.WithContext(ctx).Raw(query, schemas).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("list tables: %w", err)
	}
	return rows, nil
}

// GetTableColumns returns column metadata for a given table.
func (d *CatalogDao) GetTableColumns(ctx context.Context, schema, table string) ([]model.ColumnMeta, error) {
	query := `
		SELECT
			c.column_name                                AS name,
			c.data_type || CASE
				WHEN c.character_maximum_length IS NOT NULL
				THEN '(' || c.character_maximum_length || ')'
				ELSE ''
			END                                          AS type,
			(c.is_nullable = 'YES')                      AS nullable,
			EXISTS (
				SELECT 1 FROM information_schema.table_constraints tc
				JOIN information_schema.key_column_usage kcu
				  ON tc.constraint_name = kcu.constraint_name
				  AND tc.table_schema = kcu.table_schema
				WHERE tc.constraint_type = 'PRIMARY KEY'
				  AND tc.table_schema = $1
				  AND tc.table_name = $2
				  AND kcu.column_name = c.column_name
			) AS is_primary_key
		FROM information_schema.columns c
		WHERE c.table_schema = $1 AND c.table_name = $2
		ORDER BY c.ordinal_position
	`

	type colRow struct {
		Name         string
		Type         string
		Nullable     bool
		IsPrimaryKey bool
	}
	var rows []colRow
	if err := d.db.WithContext(ctx).Raw(query, schema, table).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("get columns for %s.%s: %w", schema, table, err)
	}

	cols := make([]model.ColumnMeta, len(rows))
	for i, r := range rows {
		cols[i] = model.ColumnMeta{
			Name:         r.Name,
			Type:         r.Type,
			Nullable:     r.Nullable,
			IsPrimaryKey: r.IsPrimaryKey,
		}
	}
	return cols, nil
}

// GetTableIndexes returns index metadata for a given table.
func (d *CatalogDao) GetTableIndexes(ctx context.Context, schema, table string) ([]model.IndexMeta, error) {
	query := `
		SELECT
			i.relname                          AS index_name,
			ix.indisunique                     AS is_unique,
			am.amname                          AS index_type,
			array_agg(a.attname ORDER BY k.n)  AS columns
		FROM pg_index ix
		JOIN pg_class t ON t.oid = ix.indrelid
		JOIN pg_class i ON i.oid = ix.indexrelid
		JOIN pg_namespace n ON n.oid = t.relnamespace
		JOIN pg_am am ON am.oid = i.relam
		CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n)
		JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
		WHERE n.nspname = $1 AND t.relname = $2
		GROUP BY i.relname, ix.indisunique, am.amname
		ORDER BY i.relname
	`

	type idxRow struct {
		IndexName string
		IsUnique  bool
		IndexType string
		Columns   model.StringArray
	}
	var rows []idxRow
	if err := d.db.WithContext(ctx).Raw(query, schema, table).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("get indexes for %s.%s: %w", schema, table, err)
	}

	indexes := make([]model.IndexMeta, len(rows))
	for i, r := range rows {
		indexes[i] = model.IndexMeta{
			Name:     r.IndexName,
			Columns:  []string(r.Columns),
			IsUnique: r.IsUnique,
			Type:     r.IndexType,
		}
	}
	return indexes, nil
}

// GetTimeRange queries the min/max of a time column.
// column and table must be safe SQL identifiers (validated).
func (d *CatalogDao) GetTimeRange(ctx context.Context, schema, table, column string) (*model.TimeRange, error) {
	// Validate identifiers to prevent SQL injection
	for _, id := range []string{schema, table, column} {
		if !SafeIdentifierRe.MatchString(id) {
			return nil, fmt.Errorf("unsafe identifier: %q", id)
		}
	}

	fullTable := table
	if schema != "" && schema != "public" {
		fullTable = schema + "." + table
	}

	query := fmt.Sprintf(
		"SELECT COALESCE(MIN(%s)::text, '') AS min, COALESCE(MAX(%s)::text, '') AS max FROM %s",
		column, column, fullTable,
	)

	type rangeRow struct {
		Min string
		Max string
	}
	var r rangeRow
	if err := d.db.WithContext(ctx).Raw(query).Scan(&r).Error; err != nil {
		return nil, fmt.Errorf("get time range for %s.%s: %w", schema, table, err)
	}
	if r.Min == "" && r.Max == "" {
		return nil, nil
	}
	return &model.TimeRange{Column: column, Min: r.Min, Max: r.Max}, nil
}

// GetTablespaces returns tablespace info.
func (d *CatalogDao) GetTablespaces(ctx context.Context) ([]model.TablespaceInfo, error) {
	query := `
		SELECT
			spcname AS name,
			pg_tablespace_location(oid) AS location,
			pg_tablespace_size(oid) AS total_size_bytes
		FROM pg_tablespace
		WHERE spcname NOT IN ('pg_global')
	`

	type tsRow struct {
		Name           string
		Location       string
		TotalSizeBytes int64
	}
	var rows []tsRow
	if err := d.db.WithContext(ctx).Raw(query).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("get tablespaces: %w", err)
	}

	result := make([]model.TablespaceInfo, len(rows))
	for i, r := range rows {
		result[i] = model.TablespaceInfo{
			Name:           r.Name,
			Location:       r.Location,
			TotalSizeBytes: r.TotalSizeBytes,
			TotalSize:      HumanSize(r.TotalSizeBytes),
		}
	}
	return result, nil
}

// HumanSize converts bytes to human-readable string.
func HumanSize(bytes int64) string {
	const (
		kb = 1024
		mb = kb * 1024
		gb = mb * 1024
		tb = gb * 1024
	)
	switch {
	case bytes >= tb:
		return fmt.Sprintf("%.1f TB", float64(bytes)/float64(tb))
	case bytes >= gb:
		return fmt.Sprintf("%.1f GB", float64(bytes)/float64(gb))
	case bytes >= mb:
		return fmt.Sprintf("%.1f MB", float64(bytes)/float64(mb))
	case bytes >= kb:
		return fmt.Sprintf("%.1f KB", float64(bytes)/float64(kb))
	default:
		return fmt.Sprintf("%d B", bytes)
	}
}
