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

type AdjustFactorService struct {
	*core.BaseComponent
	Dao *dao.AdjustFactorDao `infra:"dep:dao_adjust_factor"`
}

func NewAdjustFactorService() *AdjustFactorService {
	return &AdjustFactorService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_ADJUST_FACTOR, consts.COMPONENT_LOGGING),
	}
}

func (s *AdjustFactorService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("dao_adjust_factor is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *AdjustFactorService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *AdjustFactorService) BatchUpsert(ctx context.Context, list []*model.AdjustFactor) error {
	if len(list) == 0 {
		return nil
	}
	logging.Infof(ctx, "AdjustFactorService BatchUpsert count=%d", len(list))
	return s.Dao.BatchUpsert(ctx, list)
}

func (s *AdjustFactorService) Query(ctx context.Context, source string, f *model.AdjustFactorFilters, page, pageSize int) ([]*model.AdjustFactor, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 100
	}
	if pageSize > 1000 {
		pageSize = 1000
	}
	offset := (page - 1) * pageSize
	list, err := s.Dao.Query(ctx, source, f, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	count, err := s.Dao.Count(ctx, source, f)
	if err != nil {
		return nil, 0, err
	}
	return list, count, nil
}
