package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// defaultSource is the source used when a caller does not specify one. The
// AmazingData field dictionary is the first (and currently only) source
// onboarded, so it is a sensible discovery default.
const defaultSource = "amazing_data"

// queryPathForDataset returns the human-facing query API path template for a
// dataset. It is shown in the discovery response so callers know where to send
// actual data queries without having to consult external docs.
func queryPathForDataset(dataset string) string {
	switch dataset {
	case "financial_statement":
		return "/api/v2/financial/{source}/{statement_type}"
	case "corporate_action":
		return "/api/v2/corporate-action/{source}/{action_type}"
	case "equity_structure":
		return "/api/v2/equity-structure/{source}"
	default:
		return ""
	}
}

// FieldDictionaryService exposes the AmazingData field dictionary via the
// Phase 2 discovery APIs. It wraps FieldDictionaryDao with a small read
// cache and shapes the raw dictionary rows into the public discovery
// response models.
type FieldDictionaryService struct {
	*core.BaseComponent
	Dao *dao.FieldDictionaryDao `infra:"dep:dao_field_dictionary"`

	cacheMu        sync.RWMutex
	cachedDatasets []model.DatasetDictionaryEntry
	cachedAt       time.Time
	cacheTTL       time.Duration
}

func NewFieldDictionaryService() *FieldDictionaryService {
	return &FieldDictionaryService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_FIELD_DICTIONARY),
		cacheTTL:      10 * time.Minute,
	}
}

func (s *FieldDictionaryService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *FieldDictionaryService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

// resolveSource returns the effective source for a request, defaulting to
// amazing_data when the caller did not specify one.
func resolveSource(s string) string {
	if s == "" {
		return defaultSource
	}
	return s
}

// ListDatasets returns the dataset discovery response. The dataset list itself
// is cached (it changes only when migrations run); per-request shaping into
// DatasetDiscoveryEntry happens outside the cache.
func (s *FieldDictionaryService) ListDatasets(ctx context.Context, source string) (*model.DatasetDiscoveryResponse, error) {
	source = resolveSource(source)

	s.cacheMu.RLock()
	var cached []model.DatasetDictionaryEntry
	if s.cachedDatasets != nil && time.Since(s.cachedAt) < s.cacheTTL {
		cached = s.cachedDatasets
	}
	s.cacheMu.RUnlock()

	if cached == nil {
		rows, err := s.Dao.ListDatasets(ctx, "")
		if err != nil {
			return nil, err
		}
		s.cacheMu.Lock()
		s.cachedDatasets = rows
		s.cachedAt = time.Now()
		s.cacheMu.Unlock()
		cached = rows
	}

	entries := make([]model.DatasetDiscoveryEntry, 0, len(cached))
	var contractVersion string
	for _, d := range cached {
		if d.Source != source {
			continue
		}
		if contractVersion == "" {
			contractVersion = d.ContractVersion
		}
		entries = append(entries, model.DatasetDiscoveryEntry{
			Source:         d.Source,
			Dataset:        d.Dataset,
			LabelZh:        d.LabelZh,
			DataTypes:      d.DataTypes,
			StorageTable:   d.StorageTable,
			SourceDoc:      d.SourceDoc,
			FieldDiscovery: fmt.Sprintf("/api/v2/catalog/datasets/%s/fields", d.Dataset),
			Query:          queryPathForDataset(d.Dataset),
		})
	}

	return &model.DatasetDiscoveryResponse{
		GeneratedAt:     time.Now(),
		ContractVersion: contractVersion,
		Datasets:        entries,
	}, nil
}

// DiscoverFields returns the field discovery response for a single dataset,
// optionally narrowed by data_type. The include / search / comp_type_scope
// filters from the request are passed through to the DAO.
func (s *FieldDictionaryService) DiscoverFields(ctx context.Context, dataset string, p dao.FieldQueryParams) (*model.FieldDiscoveryResponse, error) {
	if dataset == "" {
		return nil, fmt.Errorf("dataset is required")
	}
	p.Dataset = dataset
	if p.Source == "" {
		p.Source = defaultSource
	}

	rows, err := s.Dao.DiscoverFields(ctx, p)
	if err != nil {
		return nil, err
	}

	fields := make([]model.FieldDiscoveryEntry, 0, len(rows))
	var contractVersion string
	var resolvedDataType string
	for _, r := range rows {
		if contractVersion == "" {
			contractVersion = r.ContractVersion
		}
		if resolvedDataType == "" && r.DataType != "" {
			resolvedDataType = r.DataType
		}
		fields = append(fields, model.FieldDiscoveryEntry{
			RawField:        r.RawField,
			CanonicalField:  r.CanonicalField,
			LabelZh:         r.LabelZh,
			Description:     r.Description,
			ValueType:       r.ValueType,
			Unit:            r.Unit,
			Scale:           r.Scale,
			EnumRef:         r.EnumRef,
			StorageLocation: r.StorageLocation,
			QueryName:       queryNameFor(r),
			IsMetadata:      r.IsMetadata,
			IsCore:          r.IsCore,
			CompTypeScope:   r.CompTypeScope,
			Aliases:         r.Aliases,
			SourceDoc:       r.SourceDoc,
			Deprecated:      r.Deprecated,
		})
	}

	return &model.FieldDiscoveryResponse{
		GeneratedAt:     time.Now(),
		Dataset:         dataset,
		Source:          p.Source,
		DataType:        resolvedDataType,
		ContractVersion: contractVersion,
		Fields:          fields,
	}, nil
}

// queryNameFor returns the token callers should use in the `fields=...` query
// parameter. Top-level fields use their canonical (snake_case) name so they
// map directly to table columns; data_json fields use the raw SDK field name
// so the query layer can resolve it through the dictionary.
func queryNameFor(r model.FieldDictionaryEntry) string {
	if r.StorageLocation == "top_level" {
		return r.CanonicalField
	}
	return r.RawField
}

// GetEnum returns the enum discovery response for a given enum_name. When the
// caller does not specify a source, amazing_data is used.
func (s *FieldDictionaryService) GetEnum(ctx context.Context, enumName, source string) (*model.EnumDiscoveryResponse, error) {
	if enumName == "" {
		return nil, fmt.Errorf("enum_name is required")
	}
	source = resolveSource(source)

	rows, err := s.Dao.GetEnum(ctx, enumName, source)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		logging.Warnf(ctx, "field-dictionary: enum %s not found for source %s", enumName, source)
	}

	values := make([]model.EnumDiscoveryEntry, 0, len(rows))
	var contractVersion string
	for _, r := range rows {
		if contractVersion == "" {
			contractVersion = r.ContractVersion
		}
		values = append(values, model.EnumDiscoveryEntry{
			Code:        r.Code,
			LabelZh:     r.LabelZh,
			Description: r.Description,
			SortOrder:   r.SortOrder,
			Deprecated:  r.Deprecated,
		})
	}

	return &model.EnumDiscoveryResponse{
		GeneratedAt:     time.Now(),
		EnumName:        enumName,
		Source:          source,
		ContractVersion: contractVersion,
		Values:          values,
	}, nil
}

// ListEnumNames returns the distinct enum names available for a source. It is
// a thin convenience wrapper used by the discovery UI / OpenAPI generation.
func (s *FieldDictionaryService) ListEnumNames(ctx context.Context, source string) ([]string, error) {
	return s.Dao.ListEnumNames(ctx, resolveSource(source))
}
