package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type MarketObservationController struct {
	*core.BaseComponent
	Svc *service.MarketObservationService `infra:"dep:svc_market_observation"`
}

func NewMarketObservationController() *MarketObservationController {
	return &MarketObservationController{
		BaseComponent: core.NewBaseComponent(
			bizConsts.COMP_CTRL_MARKET_OBSERVATION,
		),
	}
}

func (c *MarketObservationController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx)
}

func (c *MarketObservationController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

func (c *MarketObservationController) Upsert(
	w http.ResponseWriter,
	r *http.Request,
) {
	source := strings.TrimSpace(chi.URLParam(r, "source"))
	var rows []*model.MarketObservationDaily
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	for _, row := range rows {
		if row != nil {
			row.Source = source
			row.TradeDate = normalizeDateYYYYMMDD(row.TradeDate)
			if len(row.ExtraJSON) == 0 {
				row.ExtraJSON = json.RawMessage(`{}`)
			}
		}
	}
	if err := c.Svc.BatchUpsert(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"count":  len(rows),
	})
}

func marketObservationFilters(
	r *http.Request,
) (*model.MarketObservationFilters, error) {
	startDate, endDate := dailyDateRange(r)
	filters := &model.MarketObservationFilters{
		StartDate: startDate,
		EndDate:   endDate,
		ObservationTypes: splitDailyQueryValues(
			r.URL.Query().Get("observation_types"),
		),
	}
	if r.URL.Query().Has("security_ids") {
		securityIDs, err := parseUint64ListStrict(
			r.URL.Query().Get("security_ids"),
		)
		if err != nil {
			return nil, err
		}
		filters.SecurityIDs = securityIDs
	}
	return filters, nil
}

func (c *MarketObservationController) Query(
	w http.ResponseWriter,
	r *http.Request,
) {
	filters, err := marketObservationFilters(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.Query(
		r.Context(),
		strings.TrimSpace(chi.URLParam(r, "source")),
		filters,
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

func (c *MarketObservationController) LastDates(
	w http.ResponseWriter,
	r *http.Request,
) {
	securityIDs, err := parseUint64ListStrict(
		r.URL.Query().Get("security_ids"),
	)
	if err != nil || len(securityIDs) == 0 {
		writeJSON(
			w,
			http.StatusBadRequest,
			apiError{Error: "security_ids is required"},
		)
		return
	}
	updates, err := c.Svc.LastDates(
		r.Context(),
		strings.TrimSpace(chi.URLParam(r, "source")),
		securityIDs,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: updates})
}
