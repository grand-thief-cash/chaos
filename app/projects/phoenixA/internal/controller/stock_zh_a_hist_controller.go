package controller

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type StockZhAHistController struct {
	*core.BaseComponent
	StockZhAHistDailySvc *service.StockZhAHistDailyService `infra:"dep:svc_stock_zh_a_hist_daily"`
}

func NewStockZhAHistController() *StockZhAHistController {
	return &StockZhAHistController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_STOCK_ZH_A_HIST, consts.COMPONENT_LOGGING),
	}
}

func (c *StockZhAHistController) Start(ctx context.Context) error {
	if c.StockZhAHistDailySvc == nil {
		return errors.New("StockZhAHistDailySvc is nil")
	}
	return c.BaseComponent.Start(ctx) // Or c.BaseComponent.Start(ctx) if embedded pointer
}

func (c *StockZhAHistController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

func (c *StockZhAHistController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	var req model.BatchSaveRequest
	var err error
	ctx := r.Context()
	errMsg := ""

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		errMsg = "Invalid request body"
		logging.Error(ctx, errMsg)
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
		return
	}
	if req.Meta.Frequency == nil || req.Meta.Adjust == nil ||
		*req.Meta.Frequency == "" || *req.Meta.Adjust == "" {
		errMsg = "Req meta missing frequency & adjust"
		logging.Error(ctx, errMsg)
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
	}
	if len(req.Data) == 0 {
		errMsg = "Len of upsert data is 0"
		logging.Error(ctx, errMsg)
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
	}
	frequency := *req.Meta.Frequency

	if frequency == bizConsts.PERIOD_DAILY {
		err = c.StockZhAHistDailySvc.BatchUpsert(ctx, req.Meta, req.Data)
	} else if frequency == bizConsts.PERIOD_MONTHLY ||
		frequency == bizConsts.PERIOD_WEEKLY {
	} else if frequency == bizConsts.PERIOD_MIN5 ||
		frequency == bizConsts.PERIOD_MIN15 ||
		frequency == bizConsts.PERIOD_MIN30 ||
		frequency == bizConsts.PERIOD_MIN60 {
	}
	if err != nil {
		errMsg = fmt.Sprintf("Stock data upsert err: %s", err.Error())
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (c *StockZhAHistController) GetStockLastUpdate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var err error
	var dates map[string]string
	frequency := r.URL.Query().Get("frequency")
	adjust := r.URL.Query().Get("adjust")
	codesStr := r.URL.Query().Get("codes")

	if frequency == "" || adjust == "" || codesStr == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "Missing frequency or adjust or codes"})
		return
	}

	var codes []string
	codes = strings.Split(codesStr, ",")
	if len(codes) == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "Len of Codes is 0"})
		return
	}
	reqMeta := model.HistDataRequestMeta{
		Frequency: &frequency,
		Adjust:    &adjust,
		Codes:     codes,
	}

	if frequency == bizConsts.PERIOD_DAILY {
		dates, err = c.StockZhAHistDailySvc.GetLatestUpdateByCodes(ctx, &reqMeta)
	} else if frequency == bizConsts.PERIOD_MONTHLY ||
		frequency == bizConsts.PERIOD_WEEKLY {
	} else if frequency == bizConsts.PERIOD_MIN5 ||
		frequency == bizConsts.PERIOD_MIN15 ||
		frequency == bizConsts.PERIOD_MIN30 ||
		frequency == bizConsts.PERIOD_MIN60 {
	}
	if err != nil {
		errMsg := fmt.Sprintf("Get stock last update err: %s", err.Error())
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
		return
	}
	writeJSON(w, http.StatusOK, dates)
}

// GET /api/v1/stock/hist/range?code=000001&start_date=2024-01-01&end_date=2024-01-31&frequency=daily&adjust=nf&limit=1000&offset=0&fields=open,close
func (c *StockZhAHistController) GetDailyByCodeDateRange(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	q := r.URL.Query()

	code := strings.TrimSpace(q.Get("code"))
	startDate := strings.TrimSpace(q.Get("start_date"))
	endDate := strings.TrimSpace(q.Get("end_date"))
	frequency := strings.TrimSpace(q.Get("frequency"))
	adjust := strings.TrimSpace(q.Get("adjust"))
	limit, offset := parseLimitOffset(r)
	fields := parseFieldsParam(q.Get("fields"))

	if code == "" || startDate == "" || endDate == "" || frequency == "" || adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "missing code or start_date or end_date"})
		return
	}
	if startDate > endDate {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "start_date must be <= end_date"})
	}
	if limit < 0 {
		limit = 0
	}
	if offset < 0 {
		offset = 0
	}
	const maxLimit = 5000
	if limit == 0 {
		limit = 1000
	}
	if limit > maxLimit {
		limit = maxLimit
	}

	reqMeta := model.HistDataRequestMeta{
		Code:      &code,
		StartDate: &startDate,
		EndDate:   &endDate,
		Frequency: &frequency,
		Adjust:    &adjust,
		Limit:     &limit,
		Offset:    &offset,
		Fields:    fields,
	}

	list, err := c.StockZhAHistDailySvc.GetStockHist(ctx, &reqMeta)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		logging.Errorf(ctx, "GetDailyByCodeDateRange error: %+v", err)
		return
	}

	for _, it := range list {
		if it != nil {
			it.Date = normalizeDateYYYYMMDD(it.Date)
		}
	}

	// If 'fields' param is provided, trim output to those json fields.
	if len(fields) > 0 {
		trimmed := make([]map[string]any, 0, len(list))
		// always allow returning date/code even if caller forgot
		fieldSet := map[string]struct{}{}
		for _, f := range fields {
			fieldSet[f] = struct{}{}
		}
		for _, it := range list {
			if it == nil {
				continue
			}
			m := make(map[string]any, len(fieldSet))
			for f := range fieldSet {
				switch f {
				case "date":
					m["date"] = it.Date
				case "code":
					m["code"] = it.Code
				case "open":
					m["open"] = it.Open
				case "high":
					m["high"] = it.High
				case "low":
					m["low"] = it.Low
				case "close":
					m["close"] = it.Close
				case "preclose":
					m["preclose"] = it.Preclose
				case "volume":
					m["volume"] = it.Volume
				case "amount":
					m["amount"] = it.Amount
				case "turn":
					m["turn"] = it.Turn
				case "pctChg":
					m["pctChg"] = it.PctChg
				case "peTTM":
					m["peTTM"] = it.PeTTM
				case "psTTM":
					m["psTTM"] = it.PsTTM
				case "pcfNcfTTM":
					m["pcfNcfTTM"] = it.PcfNcfTTM
				case "pbMRQ":
					m["pbMRQ"] = it.PbMRQ
				}
			}
			trimmed = append(trimmed, m)
		}
		writeJSON(w, http.StatusOK, apiResponse[any]{Data: trimmed})
		return
	}

	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}
