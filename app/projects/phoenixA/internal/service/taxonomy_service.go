package service

import (
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TaxonomyService is the unified service for taxonomy categories and mappings.
type TaxonomyService struct {
	*core.BaseComponent
	Dao *dao.TaxonomyDao `infra:"dep:dao_taxonomy"`
}

func NewTaxonomyService() *TaxonomyService {
	return &TaxonomyService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_TAXONOMY, consts.COMPONENT_LOGGING),
	}
}

func (s *TaxonomyService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_taxonomy is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *TaxonomyService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

// BatchUpsertCategories upserts taxonomy categories.
func (s *TaxonomyService) BatchUpsertCategories(ctx context.Context, source, taxonomy, market string, list []*model.TaxonomyCategory) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertCategories source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertCategories(ctx, source, taxonomy, market, list)
}

// ListCategories lists taxonomy categories.
func (s *TaxonomyService) ListCategories(ctx context.Context, source, taxonomy, market string, f *model.TaxonomyCategoryFilters, page, pageSize int) ([]*model.TaxonomyCategory, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.ListCategories(ctx, source, taxonomy, market, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.CountCategories(ctx, source, taxonomy, market, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}

// GetCategory retrieves a single category.
func (s *TaxonomyService) GetCategory(ctx context.Context, source, taxonomy, market, code string) (*model.TaxonomyCategory, error) {
	return s.Dao.GetCategory(ctx, source, taxonomy, market, code)
}

// DeleteCategory deletes a category.
func (s *TaxonomyService) DeleteCategory(ctx context.Context, source, taxonomy, market, code string) error {
	return s.Dao.DeleteCategory(ctx, source, taxonomy, market, code)
}

// BatchUpsertMappings upserts taxonomy-security mappings.
func (s *TaxonomyService) BatchUpsertMappings(ctx context.Context, source, taxonomy string, list []*model.TaxonomySecurityMap) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	return s.Dao.BatchUpsertMappings(ctx, source, taxonomy, list)
}

// ReplaceStocksForCategories replaces all symbols for given categories.
func (s *TaxonomyService) ReplaceStocksForCategories(ctx context.Context, source, taxonomy string, payload map[string][]string) error {
	return s.Dao.ReplaceStocksForCategories(ctx, source, taxonomy, payload)
}

// ReplaceCategoriesForSymbols replaces all categories for given symbols.
func (s *TaxonomyService) ReplaceCategoriesForSymbols(ctx context.Context, source, taxonomy string, payload map[string][]string) error {
	return s.Dao.ReplaceCategoriesForSymbols(ctx, source, taxonomy, payload)
}

// ListMappingsByCategory returns mappings for a source + taxonomy + category.
func (s *TaxonomyService) ListMappingsByCategory(ctx context.Context, source, taxonomy, categoryCode string, page, pageSize int) ([]*model.TaxonomySecurityMap, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	offset := (page - 1) * pageSize
	return s.Dao.ListMappingsByCategory(ctx, source, taxonomy, categoryCode, pageSize, offset)
}

// ListMappingsBySymbol returns all taxonomy mappings for a given symbol.
func (s *TaxonomyService) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMap, error) {
	return s.Dao.ListMappingsBySymbol(ctx, symbol)
}

// DeleteMapping deletes a single mapping.
func (s *TaxonomyService) DeleteMapping(ctx context.Context, source, taxonomy, categoryCode, symbol string) error {
	return s.Dao.DeleteMapping(ctx, source, taxonomy, categoryCode, symbol)
}

// ──────────── Industry Constituents ────────────

// BatchUpsertConstituents upserts industry index constituents.
func (s *TaxonomyService) BatchUpsertConstituents(ctx context.Context, source, taxonomy, market string, list []*model.IndustryConstituent) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertConstituents source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertConstituents(ctx, source, taxonomy, market, list)
}

// ListConstituentsByIndex returns all constituents for an index.
func (s *TaxonomyService) ListConstituentsByIndex(ctx context.Context, source, taxonomy, indexCode string, page, pageSize int) ([]*model.IndustryConstituent, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	offset := (page - 1) * pageSize
	return s.Dao.ListConstituentsByIndex(ctx, source, taxonomy, indexCode, pageSize, offset)
}

// ListConstituentsBySymbol returns all index memberships for a constituent stock.
func (s *TaxonomyService) ListConstituentsBySymbol(ctx context.Context, source, taxonomy, symbol string) ([]*model.IndustryConstituent, error) {
	return s.Dao.ListConstituentsBySymbol(ctx, source, taxonomy, symbol)
}

// ──────────── Industry Weights ────────────

// BatchUpsertWeights upserts industry index constituent daily weights.
func (s *TaxonomyService) BatchUpsertWeights(ctx context.Context, source, taxonomy, market string, list []*model.IndustryWeight) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertWeights source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertWeights(ctx, source, taxonomy, market, list)
}

// ListWeightsByIndexAndDate returns weights for a given index on a given trade_date.
func (s *TaxonomyService) ListWeightsByIndexAndDate(ctx context.Context, source, taxonomy, indexCode, tradeDate string) ([]*model.IndustryWeight, error) {
	return s.Dao.ListWeightsByIndexAndDate(ctx, source, taxonomy, indexCode, tradeDate)
}

// ──────────── Industry Daily ────────────

// BatchUpsertIndustryDaily upserts industry index daily bars.
func (s *TaxonomyService) BatchUpsertIndustryDaily(ctx context.Context, source, taxonomy, market string, list []*model.IndustryDaily) error {
	if source == "" || taxonomy == "" {
		return errors.New("source and taxonomy are required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertIndustryDaily source=%s taxonomy=%s market=%s count=%d", source, taxonomy, market, len(list))
	return s.Dao.BatchUpsertIndustryDaily(ctx, source, taxonomy, market, list)
}

// QueryIndustryDaily queries industry daily bars.
func (s *TaxonomyService) QueryIndustryDaily(ctx context.Context, source, taxonomy, indexCode, startDate, endDate string, limit int) ([]*model.IndustryDaily, error) {
	if limit < 1 {
		limit = 5000
	}
	return s.Dao.QueryIndustryDaily(ctx, source, taxonomy, indexCode, startDate, endDate, limit)
}
