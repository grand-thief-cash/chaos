package dao

import (
	"context"
	"fmt"
	"sort"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
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

// SchemaDao discovers fields stored in JSON columns.
type SchemaDao struct {
	*core.BaseComponent
	GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
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

// DiscoverFields queries the database for distinct JSON keys in data_json.
// It samples up to sampleSize rows to avoid full table scans.
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

	// Extract distinct JSON keys from sampled rows
	// MySQL JSON_KEYS returns an array of keys per row; we union them across rows.
	query := fmt.Sprintf(`
		SELECT DISTINCT jk.field_name
		FROM (
			SELECT data_json FROM %s WHERE %s = ? LIMIT ?
		) sub,
		JSON_TABLE(
			JSON_KEYS(sub.data_json), '$[*]'
			COLUMNS (field_name VARCHAR(128) PATH '$')
		) jk
		ORDER BY jk.field_name
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
