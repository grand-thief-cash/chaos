package service

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

type StrategyRunService struct {
	*core.BaseComponent
	Dao *dao.StrategyRunDao `infra:"dep:dao_strategy_run"`
}

func NewStrategyRunService() *StrategyRunService {
	return &StrategyRunService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_STRATEGY_RUN, consts.COMPONENT_LOGGING),
	}
}

func (s *StrategyRunService) Start(ctx context.Context) error {
	if s.Dao == nil {
		return errors.New("the dao dao_strategy_run is nil")
	}
	return s.BaseComponent.Start(ctx)
}

func (s *StrategyRunService) Stop(ctx context.Context) error {
	return s.BaseComponent.Stop(ctx)
}

func (s *StrategyRunService) UpsertSummary(ctx context.Context, summary *model.StrategyRunSummary) error {
	if summary == nil {
		return errors.New("summary is required")
	}
	if strings.TrimSpace(summary.RunID) == "" {
		return errors.New("run_id is required")
	}
	if strings.TrimSpace(summary.TaskCode) == "" || strings.TrimSpace(summary.StrategyCode) == "" {
		return errors.New("task_code and strategy_code are required")
	}
	if strings.TrimSpace(summary.Symbol) == "" {
		return errors.New("symbol is required")
	}
	if strings.TrimSpace(summary.Status) == "" {
		return errors.New("status is required")
	}
	return s.Dao.UpsertSummary(ctx, summary)
}

func (s *StrategyRunService) UpsertArtifacts(ctx context.Context, artifacts []*model.StrategyRunArtifact) error {
	if len(artifacts) == 0 {
		return nil
	}
	allowed := map[string]struct{}{
		"analyzers":     {},
		"trades":        {},
		"orders":        {},
		"equity_curve":  {},
		"signals":       {},
		"diagnostics":   {},
		"plot_manifest": {},
		"plot_series":   {},
	}
	for _, item := range artifacts {
		if item == nil {
			return errors.New("artifact item cannot be nil")
		}
		if strings.TrimSpace(item.RunID) == "" {
			return errors.New("artifact run_id is required")
		}
		if _, ok := allowed[strings.TrimSpace(item.ArtifactType)]; !ok {
			return fmt.Errorf("unsupported artifact_type: %s", item.ArtifactType)
		}
		if strings.TrimSpace(item.PayloadVersion) == "" {
			item.PayloadVersion = "v1"
		}
		if strings.TrimSpace(item.PayloadJSON) == "" {
			return fmt.Errorf("payload_json is required for artifact_type=%s", item.ArtifactType)
		}
	}
	return s.Dao.UpsertArtifacts(ctx, artifacts)
}

func (s *StrategyRunService) GetSummary(ctx context.Context, runID string) (*model.StrategyRunSummary, error) {
	return s.Dao.GetSummary(ctx, runID)
}

func (s *StrategyRunService) ListSummaries(ctx context.Context, filter *model.StrategyRunSummaryFilters, limit, offset int) ([]*model.StrategyRunSummary, error) {
	return s.Dao.ListSummaries(ctx, filter, limit, offset)
}

func (s *StrategyRunService) ListArtifactsByRunID(ctx context.Context, runID string) ([]*model.StrategyRunArtifact, error) {
	if strings.TrimSpace(runID) == "" {
		return nil, errors.New("run_id is required")
	}
	return s.Dao.ListArtifactsByRunID(ctx, runID)
}
