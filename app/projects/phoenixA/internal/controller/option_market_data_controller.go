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

type OptionMarketDataController struct {
	*core.BaseComponent
	Svc *service.OptionMarketDataService `infra:"dep:svc_option_market_data"`
}

func NewOptionMarketDataController() *OptionMarketDataController {
	return &OptionMarketDataController{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_CTRL_OPTION_MARKET_DATA,
		),
	}
}

func (c *OptionMarketDataController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}

func (c *OptionMarketDataController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

func optionMarketDataFilters(r *http.Request) *model.OptionMarketDataFilters {
	startDate, endDate := dailyDateRange(r)
	return &model.OptionMarketDataFilters{
		StartDate: startDate,
		EndDate:   endDate,
		Symbols:   splitDailyQueryValues(r.URL.Query().Get("symbols")),
		Exchanges: splitDailyQueryValues(r.URL.Query().Get("exchanges")),
	}
}

func (c *OptionMarketDataController) UpsertOptionQVIX(
	w http.ResponseWriter,
	r *http.Request,
) {
	var rows []*model.OptionQVIXDaily
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	if err := c.Svc.BatchUpsertOptionQVIX(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"count":  len(rows),
	})
}

func (c *OptionMarketDataController) QueryOptionQVIX(
	w http.ResponseWriter,
	r *http.Request,
) {
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.QueryOptionQVIX(
		r.Context(),
		optionMarketDataFilters(r),
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

func (c *OptionMarketDataController) LastOptionQVIXDates(
	w http.ResponseWriter,
	r *http.Request,
) {
	updates, err := c.Svc.LastOptionQVIXDates(
		r.Context(),
		splitDailyQueryValues(r.URL.Query().Get("symbols")),
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: updates})
}

func (c *OptionMarketDataController) UpsertOptionDailyStats(
	w http.ResponseWriter,
	r *http.Request,
) {
	var rows []*model.OptionDailyStats
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	for _, row := range rows {
		if row != nil {
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
		}
	}
	if err := c.Svc.BatchUpsertOptionDailyStats(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"count":  len(rows),
	})
}

func (c *OptionMarketDataController) QueryOptionDailyStats(
	w http.ResponseWriter,
	r *http.Request,
) {
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.QueryOptionDailyStats(
		r.Context(),
		optionMarketDataFilters(r),
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

func (c *OptionMarketDataController) LastOptionDailyStatsDates(
	w http.ResponseWriter,
	r *http.Request,
) {
	updates, err := c.Svc.LastOptionDailyStatsDates(
		r.Context(),
		splitDailyQueryValues(r.URL.Query().Get("exchanges")),
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: updates})
}
