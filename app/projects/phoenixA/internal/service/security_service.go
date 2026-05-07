package service

import (
	"context"
	"errors"
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// SecurityService handles business logic for the unified security registry.
type SecurityService struct {
	*core.BaseComponent
	Dao *dao.SecurityRegistryDao `infra:"dep:dao_security_registry"`
}

func NewSecurityService() *SecurityService {
	return &SecurityService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SECURITY, consts.COMPONENT_LOGGING),
	}
}

func (s *SecurityService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_security_registry is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *SecurityService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *SecurityService) BatchUpsert(ctx context.Context, list []*model.SecurityRegistry, chunkSize int) (int64, error) {
	logging.Infof(ctx, "SecurityService BatchUpsert %d records", len(list))
	return s.Dao.BatchUpsert(ctx, list, chunkSize)
}

func (s *SecurityService) Get(ctx context.Context, symbol, assetType, market string) (*model.SecurityRegistry, error) {
	if assetType == "" {
		assetType = bizConsts.ASSET_TYPE_STOCK
	}
	if market == "" {
		market = bizConsts.MARKET_ZH_A
	}
	return s.Dao.Get(ctx, symbol, assetType, market)
}

func (s *SecurityService) ListFiltered(ctx context.Context, f *model.SecurityFilters, limit, offset int) ([]*model.SecurityRegistry, error) {
	return s.Dao.ListFiltered(ctx, f, limit, offset)
}

func (s *SecurityService) CountFiltered(ctx context.Context, f *model.SecurityFilters) (int64, error) {
	return s.Dao.CountFiltered(ctx, f)
}

func (s *SecurityService) DeleteAll(ctx context.Context, assetType, market string) (int64, error) {
	logging.Infof(ctx, "SecurityService DeleteAll asset_type=%s market=%s", assetType, market)
	return s.Dao.DeleteAll(ctx, assetType, market)
}

// ConvertFromLegacy creates a SecurityRegistry from legacy StockZhAList fields.
func ConvertFromLegacy(symbol, name, exchange string) *model.SecurityRegistry {
	return &model.SecurityRegistry{
		Symbol:    symbol,
		AssetType: bizConsts.ASSET_TYPE_STOCK,
		Market:    bizConsts.MARKET_ZH_A,
		Exchange:  exchange,
		Name:      name,
		Status:    "active",
	}
}

// ConvertToLegacy converts a SecurityRegistry to legacy StockZhAList format.
func ConvertToLegacy(s *model.SecurityRegistry) map[string]any {
	return map[string]any{
		"code":     s.Symbol,
		"company":  s.Name,
		"exchange": s.Exchange,
	}
}

// ConvertToLegacyList converts a list of SecurityRegistry to legacy format.
func ConvertToLegacyList(list []*model.SecurityRegistry) []map[string]any {
	out := make([]map[string]any, 0, len(list))
	for _, s := range list {
		out = append(out, map[string]any{
			"code":     s.Symbol,
			"company":  s.Name,
			"exchange": s.Exchange,
		})
	}
	return out
}

// LegacyBatchUpsertFromStockList handles legacy /api/v1/stock/list/batch_upsert payload.
func (s *SecurityService) LegacyBatchUpsertFromStockList(ctx context.Context, legacyList []map[string]any) (int64, error) {
	var list []*model.SecurityRegistry
	for _, item := range legacyList {
		symbol, _ := item["code"].(string)
		name, _ := item["company"].(string)
		exchange, _ := item["exchange"].(string)
		if symbol == "" {
			continue
		}
		list = append(list, ConvertFromLegacy(symbol, name, exchange))
	}
	if len(list) == 0 {
		return 0, fmt.Errorf("no valid items in batch")
	}
	return s.BatchUpsert(ctx, list, 200)
}
