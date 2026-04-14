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

// BatchUpsertCategories upserts taxonomy categories for a given source.
func (s *TaxonomyService) BatchUpsertCategories(ctx context.Context, source string, list []*model.TaxonomyCategory) error {
	if source == "" {
		return errors.New("source is required")
	}
	logging.Infof(ctx, "TaxonomyService BatchUpsertCategories source=%s count=%d", source, len(list))
	return s.Dao.BatchUpsertCategories(ctx, source, list)
}

// ListCategories lists taxonomy categories for a given source.
func (s *TaxonomyService) ListCategories(ctx context.Context, source string, f *model.TaxonomyCategoryFilters, page, pageSize int) ([]*model.TaxonomyCategory, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.ListCategories(ctx, source, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.CountCategories(ctx, source, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}

// GetCategory retrieves a single category by source + code.
func (s *TaxonomyService) GetCategory(ctx context.Context, source, code string) (*model.TaxonomyCategory, error) {
	return s.Dao.GetCategory(ctx, source, code)
}

// DeleteCategory deletes a category by source + code.
func (s *TaxonomyService) DeleteCategory(ctx context.Context, source, code string) error {
	return s.Dao.DeleteCategory(ctx, source, code)
}

// BatchUpsertMappings upserts taxonomy-security mappings.
func (s *TaxonomyService) BatchUpsertMappings(ctx context.Context, source string, list []*model.TaxonomySecurityMap) error {
	if source == "" {
		return errors.New("source is required")
	}
	return s.Dao.BatchUpsertMappings(ctx, source, list)
}

// ReplaceStocksForCategories replaces all symbols for given categories under a source.
func (s *TaxonomyService) ReplaceStocksForCategories(ctx context.Context, source string, payload map[string][]string) error {
	return s.Dao.ReplaceStocksForCategories(ctx, source, payload)
}

// ReplaceCategoriesForSymbols replaces all categories for given symbols under a source.
func (s *TaxonomyService) ReplaceCategoriesForSymbols(ctx context.Context, source string, payload map[string][]string) error {
	return s.Dao.ReplaceCategoriesForSymbols(ctx, source, payload)
}

// ListMappingsByCategory returns mappings for a source + category.
func (s *TaxonomyService) ListMappingsByCategory(ctx context.Context, source, categoryCode string, page, pageSize int) ([]*model.TaxonomySecurityMap, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	offset := (page - 1) * pageSize
	return s.Dao.ListMappingsByCategory(ctx, source, categoryCode, pageSize, offset)
}

// ListMappingsBySymbol returns all taxonomy mappings for a given symbol.
func (s *TaxonomyService) ListMappingsBySymbol(ctx context.Context, symbol string) ([]*model.TaxonomySecurityMap, error) {
	return s.Dao.ListMappingsBySymbol(ctx, symbol)
}

// DeleteMapping deletes a single mapping.
func (s *TaxonomyService) DeleteMapping(ctx context.Context, source, categoryCode, symbol string) error {
	return s.Dao.DeleteMapping(ctx, source, categoryCode, symbol)
}
