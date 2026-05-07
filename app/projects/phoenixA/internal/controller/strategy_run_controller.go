package controller

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"gorm.io/gorm"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// StrategyRunController 策略回测结果 HTTP 接口，提供回测摘要和制品的写入与查询 API。
type StrategyRunController struct {
	*core.BaseComponent
	Svc *service.StrategyRunService `infra:"dep:svc_strategy_run"`
}

// NewStrategyRunController 创建策略回测控制器实例。
func NewStrategyRunController() *StrategyRunController {
	return &StrategyRunController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_STRATEGY_RUN)}
}

func (c *StrategyRunController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *StrategyRunController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// UpsertSummary 新增或更新回测汇总记录。
func (c *StrategyRunController) UpsertSummary(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req model.StrategyRunSummary
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if err := c.Svc.UpsertSummary(ctx, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"run_id": req.RunID, "status": "ok"}})
}

// UpsertArtifacts 批量新增或更新回测制品。
func (c *StrategyRunController) UpsertArtifacts(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req []*model.StrategyRunArtifact
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if err := c.Svc.UpsertArtifacts(ctx, req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: map[string]any{"count": len(req), "status": "ok"}})
}

// GetSummary 根据 runID 查询回测汇总记录。
func (c *StrategyRunController) GetSummary(w http.ResponseWriter, r *http.Request, runID string) {
	ctx := r.Context()
	item, err := c.Svc.GetSummary(ctx, runID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeJSON(w, http.StatusNotFound, apiError{Error: "not found"})
			return
		}
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: item})
}

// ListSummaries 根据查询参数分页查询回测汇总列表。
func (c *StrategyRunController) ListSummaries(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	q := r.URL.Query()
	limit, offset := parseLimitOffset(r)
	if limit <= 0 {
		limit = 100
	}
	filter := &model.StrategyRunSummaryFilters{
		RunID:        strings.TrimSpace(q.Get("run_id")),
		ParentRunID:  strings.TrimSpace(q.Get("parent_run_id")),
		StrategyCode: strings.TrimSpace(q.Get("strategy_code")),
		Symbol:       strings.TrimSpace(q.Get("symbol")),
		Status:       strings.TrimSpace(q.Get("status")),
	}
	list, err := c.Svc.ListSummaries(ctx, filter, limit, offset)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}

// ListArtifacts 根据 runID 查询该次回测的所有制品。
func (c *StrategyRunController) ListArtifacts(w http.ResponseWriter, r *http.Request, runID string) {
	ctx := r.Context()
	list, err := c.Svc.ListArtifactsByRunID(ctx, runID)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}
