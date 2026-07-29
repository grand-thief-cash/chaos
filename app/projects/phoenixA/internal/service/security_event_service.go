package service

import (
	"bytes"
	"context"
	"errors"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type SecurityEventService struct {
	*core.BaseComponent
	Dao     *dao.SecurityEventDao `infra:"dep:dao_security_event"`
	Resolve *ResolveCache         `infra:"dep:svc_resolve_cache"`
}

func NewSecurityEventService() *SecurityEventService {
	return &SecurityEventService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_SECURITY_EVENT, consts.COMPONENT_LOGGING),
	}
}
func (s *SecurityEventService) Start(ctx context.Context) error {
	if s.Dao == nil || s.Resolve == nil {
		return errors.New("security event dependencies are nil")
	}
	return s.BaseComponent.Start(ctx)
}
func (s *SecurityEventService) Stop(ctx context.Context) error { return s.BaseComponent.Stop(ctx) }

func (s *SecurityEventService) BatchUpsert(ctx context.Context, rows []*model.SecurityEvent) error {
	ids := make([]uint64, 0, len(rows))
	for _, row := range rows {
		if row == nil || row.SecurityID == 0 || row.EventDate == "" || row.Title == "" {
			return NewValidationError("security_id, event_date and title are required")
		}
		if len(bytes.TrimSpace(row.DataJSON)) == 0 {
			row.DataJSON = []byte("{}")
		}
		ids = append(ids, row.SecurityID)
	}
	if err := s.Resolve.ValidateSecurityIDsExist(ctx, ids); err != nil {
		return err
	}
	return s.Dao.BatchUpsert(ctx, rows)
}

func (s *SecurityEventService) Query(
	ctx context.Context, source, eventType string, f *model.SecurityEventFilters, limit, offset int,
) ([]*model.SecurityEvent, error) {
	if limit <= 0 || limit > 5000 {
		limit = 1000
	}
	return s.Dao.Query(ctx, source, eventType, f, limit, offset)
}

func (s *SecurityEventService) LastDatesBySecurityIDs(
	ctx context.Context,
	source, eventType string,
	securityIDs []uint64,
) ([]*model.SecurityEventLastUpdate, error) {
	if len(securityIDs) == 0 {
		return nil, NewValidationError("security_ids is required")
	}
	return s.Dao.LastDatesBySecurityIDs(
		ctx,
		source,
		eventType,
		securityIDs,
	)
}
