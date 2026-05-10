package dao

import (
	"context"
	"fmt"
	"sort"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"gorm.io/gorm"
)

// domainSpec maps a domain name to its table + type discriminator column.
type domainSpec struct {
	Table      string
	TypeColumn string
}

// allowed domains — prevents arbitrary table access.
var domainAllowList = map[string]domainSpec{
	"financial_statement": {Table: "financial_statement", TypeColumn: "statement_type"},
	"corporate_action":    {Table: "corporate_action", TypeColumn: "action_type"},
}

// SchemaDao discovers fields stored in JSONB columns.
type SchemaDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewSchemaDao(dsName string) *SchemaDao {
	return &SchemaDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_SCHEMA),
		dsName:        dsName,
	}
}

func (d *SchemaDao) Start(ctx context.Context) error {
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

func (d *SchemaDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// FieldsResult holds the result of a field discovery query.
type FieldsResult struct {
	Domain      string   `json:"domain"`
	DataType    string   `json:"type"`
	Fields      []string `json:"fields"`
	SampleCount int64    `json:"sample_count"`
}

// DiscoverFields queries the database for distinct JSONB keys in data_json.
// Uses PostgreSQL jsonb_object_keys() — far more efficient than MySQL JSON_TABLE.
func (d *SchemaDao) DiscoverFields(ctx context.Context, domain, dataType string, sampleSize int) (*FieldsResult, error) {
	spec, ok := domainAllowList[domain]
	if !ok {
		return nil, fmt.Errorf("unknown domain: %s (allowed: financial_statement, corporate_action)", domain)
	}

	if sampleSize <= 0 {
		sampleSize = 500
	}

	// Count total rows for this type
	var totalCount int64
	countSQL := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s = ?", spec.Table, spec.TypeColumn)
	if err := d.db.WithContext(ctx).Raw(countSQL, dataType).Scan(&totalCount).Error; err != nil {
		return nil, fmt.Errorf("count query failed: %w", err)
	}

	if totalCount == 0 {
		return &FieldsResult{Domain: domain, DataType: dataType, Fields: []string{}, SampleCount: 0}, nil
	}

	// Extract distinct JSONB keys using PostgreSQL jsonb_object_keys()
	// data_json may be stored as a JSONB string (double-encoded) instead of native object.
	// Normalize: if 'object' use directly; if 'string' parse inner content.
	query := fmt.Sprintf(`
		SELECT DISTINCT k AS field_name
		FROM (
			SELECT
				CASE jsonb_typeof(data_json)
					WHEN 'object' THEN data_json
					WHEN 'string' THEN (data_json #>> '{}')::jsonb
				END AS data_json
			FROM %s
			WHERE %s = $1
			  AND jsonb_typeof(data_json) IN ('object', 'string')
			LIMIT $2
		) sub,
		LATERAL jsonb_object_keys(sub.data_json) AS k
		ORDER BY field_name
	`, spec.Table, spec.TypeColumn)

	var fields []string
	if err := d.db.WithContext(ctx).Raw(query, dataType, sampleSize).Scan(&fields).Error; err != nil {
		return nil, fmt.Errorf("fields discovery query failed: %w", err)
	}

	actualSampled := totalCount
	if int64(sampleSize) < totalCount {
		actualSampled = int64(sampleSize)
	}
	return &FieldsResult{
		Domain:      domain,
		DataType:    dataType,
		Fields:      fields,
		SampleCount: actualSampled,
	}, nil
}

// ListTypes returns distinct type values for a domain.
func (d *SchemaDao) ListTypes(ctx context.Context, domain string) ([]string, error) {
	spec, ok := domainAllowList[domain]
	if !ok {
		return nil, fmt.Errorf("unknown domain: %s", domain)
	}

	query := fmt.Sprintf("SELECT DISTINCT %s FROM %s ORDER BY %s", spec.TypeColumn, spec.Table, spec.TypeColumn)
	var types []string
	if err := d.db.WithContext(ctx).Raw(query).Scan(&types).Error; err != nil {
		return nil, fmt.Errorf("list types query failed: %w", err)
	}
	return types, nil
}

// ListDomains returns all allowed domain names.
func (d *SchemaDao) ListDomains() []string {
	out := make([]string, 0, len(domainAllowList))
	for k := range domainAllowList {
		out = append(out, k)
	}
	return out
}

// DomainOverview returns a summary of all domains + their types + field counts.
type DomainSummary struct {
	Domain string     `json:"domain"`
	Types  []TypeInfo `json:"types"`
}

type TypeInfo struct {
	Type       string `json:"type"`
	RowCount   int64  `json:"row_count"`
	FieldCount int    `json:"field_count"`
}

func (d *SchemaDao) Overview(ctx context.Context) ([]DomainSummary, error) {
	var summaries []DomainSummary
	for domain, spec := range domainAllowList {
		types, err := d.ListTypes(ctx, domain)
		if err != nil {
			return nil, err
		}
		var typeInfos []TypeInfo
		for _, t := range types {
			var cnt int64
			countSQL := fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE %s = ?", spec.Table, spec.TypeColumn)
			if err := d.db.WithContext(ctx).Raw(countSQL, t).Scan(&cnt).Error; err != nil {
				return nil, fmt.Errorf("overview count query for %s/%s failed: %w", domain, t, err)
			}

			// Get field count from a small sample
			result, err := d.DiscoverFields(ctx, domain, t, 50)
			if err != nil {
				return nil, fmt.Errorf("overview field discovery for %s/%s failed: %w", domain, t, err)
			}
			fieldCount := 0
			if result != nil {
				fieldCount = len(result.Fields)
			}
			typeInfos = append(typeInfos, TypeInfo{Type: t, RowCount: cnt, FieldCount: fieldCount})
		}
		summaries = append(summaries, DomainSummary{Domain: domain, Types: typeInfos})
	}

	// Sort for deterministic output
	sort.Slice(summaries, func(i, j int) bool {
		return summaries[i].Domain < summaries[j].Domain
	})
	return summaries, nil
}

// ─── Generic JSONB Discovery ───

// JSONBKeyInfo describes a single key discovered in a JSONB column.
type JSONBKeyInfo struct {
	Name       string   `json:"name"`
	ValueType  string   `json:"value_type"`  // "string", "number", "boolean", "null", "object", "array"
	SampleVals []string `json:"sample_vals"` // up to 3 sample values (stringified)
}

// DiscoverJSONBKeysGeneric discovers keys in any JSONB column of any table.
// schema.table.column must pass the safeIdentifierRe check.
func (d *SchemaDao) DiscoverJSONBKeysGeneric(ctx context.Context, schema, table, column string, sampleSize int) ([]JSONBKeyInfo, error) {
	for _, id := range []string{schema, table, column} {
		if !SafeIdentifierRe.MatchString(id) {
			return nil, fmt.Errorf("unsafe identifier: %q", id)
		}
	}
	if sampleSize <= 0 {
		sampleSize = 200
	}

	fullTable := table
	if schema != "" && schema != "public" {
		fullTable = schema + "." + table
	}

	// Discover distinct keys and infer types via jsonb_typeof
	// data_json may be stored as JSONB string — normalize with CASE.
	// Use ?? for PostgreSQL JSONB ? operator (GORM would eat single ? as placeholder).
	query := fmt.Sprintf(`
		SELECT
			k AS key_name,
			COALESCE(
				(SELECT jsonb_typeof(norm.norm_col -> k)
				 FROM (
					SELECT
						CASE jsonb_typeof(t.%[4]s)
							WHEN 'object' THEN t.%[4]s
							WHEN 'string' THEN (t.%[4]s #>> '{}')::jsonb
						END AS norm_col
					FROM %[1]s t
					WHERE t.%[4]s ?? k AND jsonb_typeof(t.%[4]s) IN ('object', 'string')
					LIMIT 1
				 ) norm),
				'null'
			) AS value_type
		FROM (
			SELECT DISTINCT k
			FROM (
				SELECT
					CASE jsonb_typeof(%[4]s)
						WHEN 'object' THEN %[4]s
						WHEN 'string' THEN (%[4]s #>> '{}')::jsonb
					END AS %[4]s
				FROM %[2]s
				WHERE %[4]s IS NOT NULL AND jsonb_typeof(%[4]s) IN ('object', 'string')
				LIMIT $1
			) sub,
			LATERAL jsonb_object_keys(sub.%[4]s) AS k
		) keys
		ORDER BY key_name
	`, fullTable, fullTable, column, column)

	type keyRow struct {
		KeyName   string
		ValueType string
	}
	var rows []keyRow
	if err := d.db.WithContext(ctx).Raw(query, sampleSize).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("generic jsonb discovery for %s.%s.%s: %w", schema, table, column, err)
	}

	result := make([]JSONBKeyInfo, 0, len(rows))
	for _, r := range rows {
		info := JSONBKeyInfo{
			Name:      r.KeyName,
			ValueType: r.ValueType,
		}

		// Get sample values (up to 3 distinct non-null)
		// Use ?? for PostgreSQL JSONB ? operator (GORM eats single ?)
		sampleQuery := fmt.Sprintf(
			`SELECT DISTINCT (norm.%[3]s ->> $1)::text AS val
			 FROM (
				SELECT
					CASE jsonb_typeof(t.%[3]s)
						WHEN 'object' THEN t.%[3]s
						WHEN 'string' THEN (t.%[3]s #>> '{}')::jsonb
					END AS %[3]s
				FROM %[2]s t
				WHERE t.%[3]s ?? $1 AND jsonb_typeof(t.%[3]s) IN ('object', 'string')
			 ) norm
			 WHERE (norm.%[3]s ->> $1) IS NOT NULL
			 LIMIT 3`,
			column, fullTable, column, column,
		)
		var samples []string
		if err := d.db.WithContext(ctx).Raw(sampleQuery, r.KeyName).Scan(&samples).Error; err == nil {
			info.SampleVals = samples
		}

		result = append(result, info)
	}
	return result, nil
}
