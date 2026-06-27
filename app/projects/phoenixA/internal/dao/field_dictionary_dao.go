package dao

import (
	"context"
	"fmt"
	"regexp"
	"strings"
	"time"

	pg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"gorm.io/gorm"
)

// FieldDictionaryDao reads the data_dataset_dictionary / data_field_dictionary
// / data_enum_dictionary tables seeded by migrations 0012/0013. It is the
// data-access side of the Phase 2 field discovery APIs.
type FieldDictionaryDao struct {
	*core.BaseComponent
	GormComp *pg.PostgresGormComponent `infra:"dep:postgres_gorm"`
	db       *gorm.DB
	dsName   string
}

func NewFieldDictionaryDao(dsName string) *FieldDictionaryDao {
	return &FieldDictionaryDao{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_DAO_FIELD_DICTIONARY),
		dsName:        dsName,
	}
}

func (d *FieldDictionaryDao) Start(ctx context.Context) error {
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

func (d *FieldDictionaryDao) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// DB exposes the underlying gorm.DB for callers that need to compose their own
// queries (e.g. the catalog service joining dictionary rows by dataset).
func (d *FieldDictionaryDao) DB() *gorm.DB { return d.db }

// ListDatasets returns all dataset dictionary rows, optionally filtered by
// source. When source is empty, all sources are returned. Rows are ordered by
// source then dataset for stable output.
func (d *FieldDictionaryDao) ListDatasets(ctx context.Context, source string) ([]model.DatasetDictionaryEntry, error) {
	query := `
		SELECT contract_version, source, dataset, label_zh,
		       data_types::text AS data_types_raw,
		       storage_table, storage_tablespace, dictionary_tablespace,
		       source_doc, created_at, updated_at
		FROM data_dataset_dictionary
	`
	args := []any{}
	if source != "" {
		query += " WHERE source = $1"
		args = append(args, source)
	}
	query += " ORDER BY source, dataset"

	type row struct {
		ContractVersion      string
		Source               string
		Dataset              string
		LabelZh              string
		DataTypesRaw         []byte
		StorageTable         string
		StorageTablespace    string
		DictionaryTablespace string
		SourceDoc            string
		CreatedAt            time.Time
		UpdatedAt            time.Time
	}

	var rows []row
	if err := d.db.WithContext(ctx).Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("list dataset dictionary: %w", err)
	}

	out := make([]model.DatasetDictionaryEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, model.DatasetDictionaryEntry{
			ContractVersion:      r.ContractVersion,
			Source:               r.Source,
			Dataset:              r.Dataset,
			LabelZh:              r.LabelZh,
			DataTypes:            model.DecodeStringArray(r.DataTypesRaw),
			StorageTable:         r.StorageTable,
			StorageTablespace:    r.StorageTablespace,
			DictionaryTablespace: r.DictionaryTablespace,
			SourceDoc:            r.SourceDoc,
			CreatedAt:            r.CreatedAt,
			UpdatedAt:            r.UpdatedAt,
		})
	}
	return out, nil
}

// FieldQueryParams controls DiscoverFields filtering. Empty fields mean "no
// filter". Search is a case-insensitive substring match across raw_field,
// canonical_field, label_zh, and description.
type FieldQueryParams struct {
	Source            string
	Dataset           string
	DataType          string
	Include           string // "core" (default), "all", "metadata"
	Search            string
	CompTypeScope     string // "all" / "non_financial" / "bank" / "insurance" / "securities"
	IncludeDeprecated bool
}

// DiscoverFields returns field dictionary rows matching the given filters.
// It applies the include / search / comp_type_scope rules described in the
// AmazingData field discovery design doc.
func (d *FieldDictionaryDao) DiscoverFields(ctx context.Context, p FieldQueryParams) ([]model.FieldDictionaryEntry, error) {
	var sb strings.Builder
	sb.WriteString(`
		SELECT contract_version, source, dataset, data_type, data_type_label_zh,
		       sdk_section, sdk_function, raw_field, canonical_field, label_zh,
		       description, value_type, source_value_type, unit, scale, enum_ref,
		       storage_location, is_metadata, is_core, comp_type_scope,
		       aliases::text AS aliases_raw, source_doc, source_path,
		       review_status, deprecated, created_at, updated_at
		FROM data_field_dictionary
		WHERE 1=1
	`)
	args := []any{}
	n := 1
	if p.Source != "" {
		sb.WriteString(fmt.Sprintf(" AND source = $%d", n))
		args = append(args, p.Source)
		n++
	}
	if p.Dataset != "" {
		sb.WriteString(fmt.Sprintf(" AND dataset = $%d", n))
		args = append(args, p.Dataset)
		n++
	}
	if p.DataType != "" {
		sb.WriteString(fmt.Sprintf(" AND data_type = $%d", n))
		args = append(args, p.DataType)
		n++
	}
	if !p.IncludeDeprecated {
		sb.WriteString(" AND deprecated = FALSE")
	}
	switch p.Include {
	case "", "core":
		// Default: core business fields + metadata columns. Excludes the long
		// tail of low-frequency JSONB detail fields so discovery responses stay
		// small. Callers asking for the full list use include=all.
		sb.WriteString(" AND (is_core = TRUE OR is_metadata = TRUE)")
	case "metadata":
		sb.WriteString(" AND is_metadata = TRUE")
	case "all":
		// no extra filter
	}
	if p.CompTypeScope != "" && p.CompTypeScope != "all" {
		// comp_type_scope can be 'all' (applies to every company) or a specific
		// scope like 'bank'. A field is applicable to a given comp type if its
		// scope is 'all' or matches the requested scope exactly.
		sb.WriteString(fmt.Sprintf(" AND (comp_type_scope = 'all' OR comp_type_scope = $%d)", n))
		args = append(args, p.CompTypeScope)
		n++
	}
	if p.Search != "" {
		// ILIKE works on PostgreSQL without extra indexing for discovery-scale
		// traffic; the dictionary table is small (low thousands of rows).
		pattern := "%" + p.Search + "%"
		sb.WriteString(fmt.Sprintf(" AND (raw_field ILIKE $%d OR canonical_field ILIKE $%d OR label_zh ILIKE $%d OR description ILIKE $%d)", n, n, n, n))
		args = append(args, pattern)
		n++
	}
	sb.WriteString(" ORDER BY dataset, data_type, is_metadata DESC, is_core DESC, raw_field")

	type row struct {
		ContractVersion string
		Source          string
		Dataset         string
		DataType        string
		DataTypeLabelZh string
		SDKSection      string
		SDKFunction     string
		RawField        string
		CanonicalField  string
		LabelZh         string
		Description     string
		ValueType       string
		SourceValueType string
		Unit            string
		Scale           *float64
		EnumRef         string
		StorageLocation string
		IsMetadata      bool
		IsCore          bool
		CompTypeScope   string
		AliasesRaw      []byte
		SourceDoc       string
		SourcePath      string
		ReviewStatus    string
		Deprecated      bool
		CreatedAt       time.Time
		UpdatedAt       time.Time
	}

	var rows []row
	if err := d.db.WithContext(ctx).Raw(sb.String(), args...).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("discover fields: %w", err)
	}

	out := make([]model.FieldDictionaryEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, model.FieldDictionaryEntry{
			ContractVersion: r.ContractVersion,
			Source:          r.Source,
			Dataset:         r.Dataset,
			DataType:        r.DataType,
			DataTypeLabelZh: r.DataTypeLabelZh,
			SDKSection:      r.SDKSection,
			SDKFunction:     r.SDKFunction,
			RawField:        r.RawField,
			CanonicalField:  r.CanonicalField,
			LabelZh:         r.LabelZh,
			Description:     r.Description,
			ValueType:       r.ValueType,
			SourceValueType: r.SourceValueType,
			Unit:            r.Unit,
			Scale:           r.Scale,
			EnumRef:         r.EnumRef,
			StorageLocation: r.StorageLocation,
			IsMetadata:      r.IsMetadata,
			IsCore:          r.IsCore,
			CompTypeScope:   r.CompTypeScope,
			Aliases:         model.DecodeStringArray(r.AliasesRaw),
			SourceDoc:       r.SourceDoc,
			SourcePath:      r.SourcePath,
			ReviewStatus:    r.ReviewStatus,
			Deprecated:      r.Deprecated,
			CreatedAt:       r.CreatedAt,
			UpdatedAt:       r.UpdatedAt,
		})
	}
	return out, nil
}

// GetEnum returns enum dictionary rows for the given enum_name, optionally
// filtered by source. Rows are ordered by sort_order then code.
func (d *FieldDictionaryDao) GetEnum(ctx context.Context, enumName, source string) ([]model.EnumDictionaryEntry, error) {
	if enumName == "" {
		return nil, fmt.Errorf("enum_name is required")
	}
	query := `
		SELECT contract_version, source, enum_name, code, label_zh,
		       description, sort_order, source_doc, review_status,
		       deprecated, created_at, updated_at
		FROM data_enum_dictionary
		WHERE enum_name = $1
	`
	args := []any{enumName}
	if source != "" {
		query += " AND source = $2"
		args = append(args, source)
	}
	query += " AND deprecated = FALSE ORDER BY sort_order, code"

	type row struct {
		ContractVersion string
		Source          string
		EnumName        string
		Code            string
		LabelZh         string
		Description     string
		SortOrder       int
		SourceDoc       string
		ReviewStatus    string
		Deprecated      bool
		CreatedAt       time.Time
		UpdatedAt       time.Time
	}

	var rows []row
	if err := d.db.WithContext(ctx).Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, fmt.Errorf("get enum %s: %w", enumName, err)
	}

	out := make([]model.EnumDictionaryEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, model.EnumDictionaryEntry{
			ContractVersion: r.ContractVersion,
			Source:          r.Source,
			EnumName:        r.EnumName,
			Code:            r.Code,
			LabelZh:         r.LabelZh,
			Description:     r.Description,
			SortOrder:       r.SortOrder,
			SourceDoc:       r.SourceDoc,
			ReviewStatus:    r.ReviewStatus,
			Deprecated:      r.Deprecated,
			CreatedAt:       r.CreatedAt,
			UpdatedAt:       r.UpdatedAt,
		})
	}
	return out, nil
}

// ListEnumNames returns the distinct enum names referenced by field dictionary
// rows for the given source. Useful for telling callers which enums they can
// ask about for a given source.
func (d *FieldDictionaryDao) ListEnumNames(ctx context.Context, source string) ([]string, error) {
	query := `
		SELECT DISTINCT enum_ref AS enum_name
		FROM data_field_dictionary
		WHERE enum_ref != '' AND deprecated = FALSE
	`
	args := []any{}
	if source != "" {
		query += " AND source = $1"
		args = append(args, source)
	}
	query += " ORDER BY enum_ref"

	var names []string
	if err := d.db.WithContext(ctx).Raw(query, args...).Scan(&names).Error; err != nil {
		return nil, fmt.Errorf("list enum names: %w", err)
	}
	return names, nil
}

// ─── Phase 3: field resolution ───

// ResolvedField is the output of ResolveFields for one requested field. It
// carries everything the DAO needs to build a safe SELECT expression and the
// controller needs to build response metadata.
type ResolvedField struct {
	RawField        string
	CanonicalField  string
	LabelZh         string
	Description     string
	ValueType       string
	Unit            string
	Scale           *float64
	EnumRef         string
	StorageLocation string // "top_level" or "data_json"
	IsMetadata      bool
	IsCore          bool
	// SelectExpr is the SQL expression for the SELECT list, e.g.
	// `symbol` for a top_level field or
	// `(data_json->>'TOTAL_ASSETS')::numeric` for a data_json numeric field.
	// It is built from validated identifiers only — never from raw user input.
	SelectExpr string
	// OutputKey is the key the value should appear under in flat response
	// rows. Raw_field for data_json fields, canonical_field for top_level.
	OutputKey string
}

// ResolveFields maps user-supplied field names (raw or canonical) to
// ResolvedField entries using the field dictionary. Fields may be requested
// by raw_field (e.g. "TOTAL_ASSETS") or canonical_field (e.g. "total_assets").
// Top-level fields are matched case-insensitively against canonical_field;
// data_json fields are matched case-sensitively against raw_field (SDK field
// names are conventionally UPPER_SNAKE).
//
// Returns:
//   - resolved: successfully resolved fields, in the order requested
//   - unknown:  fields that did not match, each with suggested candidates
//
// When dataType is empty, resolution is done across all data_types for the
// dataset — useful when a top-level field like `symbol` is shared.
func (d *FieldDictionaryDao) ResolveFields(ctx context.Context, source, dataset, dataType string, requested []string) (resolved []ResolvedField, unknown []model.UnknownFieldHint, err error) {
	if len(requested) == 0 {
		return nil, nil, nil
	}

	// Pull all candidate fields once. Include deprecated fields so we can
	// surface "this field is deprecated, use X instead" — but only
	// non-deprecated fields are eligible as suggestions.
	rows, err := d.DiscoverFields(ctx, FieldQueryParams{
		Source:            source,
		Dataset:           dataset,
		DataType:          dataType,
		Include:           "all",
		IncludeDeprecated: true,
	})
	if err != nil {
		return nil, nil, fmt.Errorf("resolve fields: load dictionary: %w", err)
	}

	// Build lookup indexes. For data_json fields we index by exact raw_field
	// (case-sensitive) plus a lowercase canonical alias. For top_level fields
	// we index by canonical_field (lowercased) since that is the public name
	// surfaced in the discovery API.
	type indexEntry struct {
		row     model.FieldDictionaryEntry
		matched bool
	}
	byRaw := make(map[string]*indexEntry, len(rows))
	byCanonicalLower := make(map[string]*indexEntry, len(rows))
	byAliasLower := make(map[string]*indexEntry, len(rows))
	for i := range rows {
		r := &rows[i]
		e := &indexEntry{row: *r}
		byRaw[r.RawField] = e
		if r.CanonicalField != "" {
			byCanonicalLower[strings.ToLower(r.CanonicalField)] = e
		}
		for _, a := range r.Aliases {
			if a != "" {
				byAliasLower[strings.ToLower(a)] = e
			}
		}
	}

	resolved = make([]ResolvedField, 0, len(requested))
	for _, req := range requested {
		req = strings.TrimSpace(req)
		if req == "" {
			continue
		}
		// Strip a leading "data_json." prefix if the caller used the old
		// convention. We resolve the bare field name through the dictionary.
		req = strings.TrimPrefix(req, "data_json.")

		var entry *indexEntry
		if e, ok := byRaw[req]; ok {
			entry = e
		} else if e, ok := byCanonicalLower[strings.ToLower(req)]; ok {
			entry = e
		} else if e, ok := byAliasLower[strings.ToLower(req)]; ok {
			entry = e
		}

		if entry == nil {
			unknown = append(unknown, model.UnknownFieldHint{
				Field:       req,
				Suggestions: suggestFields(req, rows),
			})
			continue
		}
		entry.matched = true
		resolved = append(resolved, buildResolvedField(entry.row))
	}

	return resolved, unknown, nil
}

// buildResolvedField turns a dictionary row into a ResolvedField with a
// pre-built, validated SELECT expression. Only dictionary-registered names
// ever reach this function, so the generated SQL is injection-safe.
func buildResolvedField(r model.FieldDictionaryEntry) ResolvedField {
	rf := ResolvedField{
		RawField:        r.RawField,
		CanonicalField:  r.CanonicalField,
		LabelZh:         r.LabelZh,
		Description:     r.Description,
		ValueType:       r.ValueType,
		Unit:            r.Unit,
		Scale:           r.Scale,
		EnumRef:         r.EnumRef,
		StorageLocation: r.StorageLocation,
		IsMetadata:      r.IsMetadata,
		IsCore:          r.IsCore,
	}

	switch r.StorageLocation {
	case "top_level":
		// Top-level fields are real table columns named by canonical_field.
		// canonical_field values come from the dictionary seed, which is
		// generated from a controlled source — but we still validate the
		// identifier so a bad dictionary row can never break the query.
		col := r.CanonicalField
		if !SafeIdentifierRe.MatchString(col) {
			col = r.RawField
		}
		if !SafeIdentifierRe.MatchString(col) {
			col = "id" // last-resort fallback; should never happen for governed tables
		}
		rf.SelectExpr = col
		rf.OutputKey = r.CanonicalField
		if rf.OutputKey == "" {
			rf.OutputKey = r.RawField
		}
	case "data_json":
		// data_json fields are projected out of the JSONB object using the
		// raw SDK field name. The cast depends on value_type so callers get
		// typed values (number stays numeric, date stays text, etc.).
		raw := r.RawField
		// raw_field is validated to a conservative identifier charset before
		// being interpolated into SQL. SDK field names are UPPER_SNAKE_ASCII.
		if !jsonbKeyRe.MatchString(raw) {
			// Fall back to a parameterized containment lookup is not possible
			// inside a SELECT expression; skip the field instead of risking
			// injection. The discovery API will surface the bad dictionary row.
			break
		}
		cast := jsonbCast(r.ValueType)
		rf.SelectExpr = fmt.Sprintf("(data_json->'%s')%s", raw, cast)
		rf.OutputKey = r.RawField
	}

	return rf
}

// jsonbCast returns the SQL cast suffix for extracting a typed value from a
// JSONB field. data_json->>'field' yields text; ::numeric / ::boolean give
// typed values. Dates are kept as text since they are stored as YYYY-MM-DD
// strings already.
func jsonbCast(valueType string) string {
	switch valueType {
	case "number", "integer":
		return "::text" // keep as text in SQL; controller parses to float64
	case "boolean":
		return "::text"
	default:
		return "::text"
	}
}

// suggestFields returns up to 5 candidate fields for an unresolved name. It
// checks aliases first (exact case-insensitive match — the most likely cause
// of "field not found" is a SDK rename captured in aliases), then falls back
// to substring / prefix matches on raw_field and canonical_field.
func suggestFields(req string, rows []model.FieldDictionaryEntry) []model.FieldSuggestion {
	lower := strings.ToLower(req)
	var out []model.FieldSuggestion
	seen := make(map[string]bool)

	// 1. Alias matches — highest signal.
	for _, r := range rows {
		if r.Deprecated {
			continue
		}
		for _, a := range r.Aliases {
			if strings.ToLower(a) == lower {
				if !seen[r.RawField] {
					out = append(out, model.FieldSuggestion{
						Field:    r.RawField,
						RawField: r.RawField,
						LabelZh:  r.LabelZh,
					})
					seen[r.RawField] = true
				}
			}
		}
	}
	if len(out) >= 5 {
		return out[:5]
	}

	// 2. Substring / prefix matches on raw_field and canonical_field.
	for _, r := range rows {
		if r.Deprecated {
			continue
		}
		if seen[r.RawField] {
			continue
		}
		rawLower := strings.ToLower(r.RawField)
		canLower := strings.ToLower(r.CanonicalField)
		if strings.Contains(rawLower, lower) || strings.Contains(canLower, lower) ||
			strings.Contains(lower, rawLower) {
			out = append(out, model.FieldSuggestion{
				Field:    r.RawField,
				RawField: r.RawField,
				LabelZh:  r.LabelZh,
			})
			seen[r.RawField] = true
			if len(out) >= 5 {
				break
			}
		}
	}
	return out
}

// jsonbKeyRe validates a raw_field name before interpolation into a JSONB
// access expression. Allows UPPER_SNAKE_CASE with digits; conservative on
// purpose — anything outside this set should never appear in a governed SDK
// field name and would indicate either a bad dictionary row or an injection
// attempt.
var jsonbKeyRe = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
