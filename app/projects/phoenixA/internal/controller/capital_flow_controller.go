package controller

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type CapitalFlowController struct {
	*core.BaseComponent
	Svc *service.CapitalFlowService `infra:"dep:svc_capital_flow"`
}

func NewCapitalFlowController() *CapitalFlowController {
	return &CapitalFlowController{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_CTRL_CAPITAL_FLOW,
		),
	}
}

func (c *CapitalFlowController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}

func (c *CapitalFlowController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

func capitalFlowFilters(r *http.Request) *model.CapitalFlowFilters {
	startDate, endDate := dailyDateRange(r)
	return &model.CapitalFlowFilters{
		StartDate: startDate,
		EndDate:   endDate,
		Symbols:   splitDailyQueryValues(r.URL.Query().Get("symbols")),
	}
}

func (c *CapitalFlowController) UpsertMarginSummary(
	w http.ResponseWriter,
	r *http.Request,
) {
	var rows []*model.MarginSummaryDaily
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	if err := c.Svc.BatchUpsertMarginSummary(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"count":  len(rows),
	})
}

func (c *CapitalFlowController) QueryMarginSummary(
	w http.ResponseWriter,
	r *http.Request,
) {
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.QueryMarginSummary(
		r.Context(),
		capitalFlowFilters(r),
		limit,
		offset,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows})
}

func (c *CapitalFlowController) LastMarginSummaryDate(
	w http.ResponseWriter,
	r *http.Request,
) {
	last, err := c.Svc.LastMarginSummaryDate(r.Context())
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{
		Data: map[string]string{
			"last_update": normalizeDateYYYYMMDD(last),
		},
	})
}

func (c *CapitalFlowController) UpsertHSGT(
	w http.ResponseWriter,
	r *http.Request,
) {
	var rows []*model.HSGTDaily
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	if err := c.Svc.BatchUpsertHSGT(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"count":  len(rows),
	})
}

func (c *CapitalFlowController) QueryHSGT(
	w http.ResponseWriter,
	r *http.Request,
) {
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.QueryHSGT(
		r.Context(),
		capitalFlowFilters(r),
		limit,
		offset,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows})
}

func (c *CapitalFlowController) LastHSGTDates(
	w http.ResponseWriter,
	r *http.Request,
) {
	updates, err := c.Svc.LastHSGTDates(
		r.Context(),
		splitDailyQueryValues(r.URL.Query().Get("symbols")),
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: updates})
}
