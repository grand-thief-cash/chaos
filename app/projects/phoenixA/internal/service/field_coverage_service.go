package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// FieldCoverageService scans governed datasets' data_json for observed keys,
// classifies them against the field dictionary, and exposes ungoverned keys
// as candidates for governance. Implements Phase 4 #3.
type FieldCoverageService struct {
	*core.BaseComponent
	CoverageDao  *dao.FieldCoverageDao   `infra:"dep:dao_field_coverage"`
	FieldDictDao *dao.FieldDictionaryDao `infra:"dep:dao_field_dictionary"`
}

func NewFieldCoverageService() *FieldCoverageService {
	return &FieldCoverageService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_FIELD_COVERAGE, consts.COMPONENT_LOGGING),
	}
}

func (s *FieldCoverageService) Start(ctx context.Context) error {
	if s.CoverageDao == nil {
		return errors.New("dao_field_coverage is nil")
	}
	if s.FieldDictDao == nil {
		return errors.New("dao_field_dictionary is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *FieldCoverageService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

// defaultSampleLimit caps the per-dataset scan to keep latency bounded on
// large tables. 10000 rows is enough to surface any SDK-added field that
// appears in recent data without scanning history that may use older schemas.
const defaultSampleLimit = 10000

// ScanDataset scans one dataset. If `dataset` is empty, scans all governed
// datasets found in the dataset dictionary. Returns per-dataset summaries.
func (s *FieldCoverageService) ScanDataset(ctx context.Context, dataset, source string, sampleLimit int) ([]model.FieldCoverageScanResult, error) {
	if sampleLimit <= 0 {
		sampleLimit = defaultSampleLimit
	}

	datasets, err := s.FieldDictDao.ListDatasets(ctx, source)
	if err != nil {
		return nil, fmt.Errorf("list datasets: %w", err)
	}

	var results []model.FieldCoverageScanResult
	for _, d := range datasets {
		if dataset != "" && d.Dataset != dataset {
			continue
		}
		if d.StorageTable == "" {
			continue
		}
		// Resolve governed raw_field set (storage_location=data_json).
		fields, err := s.FieldDictDao.DiscoverFields(ctx, dao.FieldQueryParams{
			Dataset: d.Dataset,
			Source:  d.Source,
		})
		if err != nil {
			logging.Warnf(ctx, "field-coverage: discover fields for %s failed: %v", d.Dataset, err)
			results = append(results, model.FieldCoverageScanResult{
				Dataset:      d.Dataset,
				Source:       d.Source,
				StorageTable: d.StorageTable,
				Error:        fmt.Sprintf("discover fields: %v", err),
			})
			continue
		}
		governed := make(map[string]bool, len(fields))
		for _, f := range fields {
			if f.StorageLocation == "data_json" {
				governed[f.RawField] = true
			}
		}

		res, err := s.CoverageDao.ScanDataset(ctx, d.Dataset, d.Source, d.StorageTable, governed, sampleLimit)
		if err != nil {
			logging.Warnf(ctx, "field-coverage: scan %s failed: %v", d.Dataset, err)
			results = append(results, model.FieldCoverageScanResult{
				Dataset:      d.Dataset,
				Source:       d.Source,
				StorageTable: d.StorageTable,
				Error:        err.Error(),
			})
			continue
		}
		logging.Infof(ctx, "field-coverage: scanned %s rows=%d keys=%d ungoverned=%d",
			d.Dataset, res.RowsScanned, res.DistinctKeys, res.UngovernedCount)
		results = append(results, *res)
	}

	if len(results) == 0 {
		return nil, fmt.Errorf("no datasets matched (dataset=%q source=%q)", dataset, source)
	}
	return results, nil
}

// ListObservations returns observed keys, optionally filtered.
func (s *FieldCoverageService) ListObservations(ctx context.Context, dataset, source, status string) (*model.FieldCoverageListResponse, error) {
	rows, err := s.CoverageDao.ListObservations(ctx, dataset, source, status)
	if err != nil {
		return nil, err
	}
	return &model.FieldCoverageListResponse{
		GeneratedAt:  time.Now(),
		Dataset:      dataset,
		StatusFilter: status,
		Count:        len(rows),
		Observations: rows,
	}, nil
}
