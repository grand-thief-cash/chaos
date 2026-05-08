package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/buffer"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

// BarsController handles HTTP endpoints for unified bars data.
type BarsController struct {
	*core.BaseComponent
	Svc       *service.BarsService       `infra:"dep:svc_bars"`
	BufferMgr *buffer.WriteBufferManager `infra:"dep:write_buffer_mgr"`
}

func NewBarsController() *BarsController {
	return &BarsController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_BARS)}
}

func (c *BarsController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *BarsController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// POST /api/v2/bars/{asset_type}/{market}/upsert
func (c *BarsController) Upsert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	assetType := chi.URLParam(r, "asset_type")
	market := chi.URLParam(r, "market")

	var req model.BarsUpsertRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	if req.Meta.Period == "" || req.Meta.Adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "meta.period and meta.adjust are required"})
		return
	}
	if len(req.Bars) == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "bars data is empty"})
		return
	}

	q := &model.BarsQuery{
		AssetType: assetType,
		Market:    market,
		Period:    req.Meta.Period,
		Adjust:    req.Meta.Adjust,
	}

	// ── Write Buffer routing ──
	// If buffer is enabled, parse bars to decide direct vs buffered path.
	if c.BufferMgr != nil && c.BufferMgr.IsEnabled() {
		var bars []*model.StandardBar
		if err := json.Unmarshal(req.Bars, &bars); err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("bars parse error: %s", err.Error())})
			return
		}

		if len(bars) >= c.BufferMgr.DirectFlushThreshold() {
			// Large batch: direct write (existing path)
			if err := c.Svc.Dao.BatchUpsert(ctx, q, bars); err != nil {
				errMsg := fmt.Sprintf("bars upsert error: %s", err.Error())
				logging.Error(ctx, errMsg)
				writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
				return
			}
			// Write extension data directly too
			if len(req.Ext) > 0 && req.Meta.Source != "" {
				if err := c.Svc.BatchUpsertExt(ctx, req.Meta.Source, q, req.Ext); err != nil {
					logging.Errorf(ctx, "bars ext upsert error: %s", err.Error())
				}
			}
		} else {
			// Small batch: submit to write buffer
			if err := c.BufferMgr.Submit(q, bars, req.Ext, req.Meta.Source); err != nil {
				logging.Errorf(ctx, "write buffer submit failed: %s", err.Error())
				writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full, retry later"})
				return
			}
		}

		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}

	// ── Original direct path (buffer disabled or nil) ──
	if err := c.Svc.BatchUpsert(ctx, q, req.Bars); err != nil {
		errMsg := fmt.Sprintf("bars upsert error: %s", err.Error())
		logging.Error(ctx, errMsg)
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
		return
	}

	// Write extension data if present
	if len(req.Ext) > 0 && req.Meta.Source != "" {
		if err := c.Svc.BatchUpsertExt(ctx, req.Meta.Source, q, req.Ext); err != nil {
			logging.Errorf(ctx, "bars ext upsert error: %s", err.Error())
			// Non-fatal: standard bars already written
		}
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// GET /api/v2/bars/{asset_type}/{market}
func (c *BarsController) Query(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	assetType := chi.URLParam(r, "asset_type")
	market := chi.URLParam(r, "market")
	qp := r.URL.Query()

	symbol := strings.TrimSpace(qp.Get("symbol"))
	startDate := strings.TrimSpace(qp.Get("start_date"))
	endDate := strings.TrimSpace(qp.Get("end_date"))
	period := strings.TrimSpace(qp.Get("period"))
	adjust := strings.TrimSpace(qp.Get("adjust"))
	limit, offset := parseLimitOffset(r)
	fields := parseFieldsParam(qp.Get("fields"))

	if symbol == "" || startDate == "" || endDate == "" || period == "" || adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "symbol, start_date, end_date, period, adjust are required"})
		return
	}
	if startDate > endDate {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "start_date must be <= end_date"})
		return
	}

	const maxLimit = 5000
	if limit <= 0 {
		limit = 1000
	}
	if limit > maxLimit {
		limit = maxLimit
	}

	q := &model.BarsQuery{
		AssetType: assetType,
		Market:    market,
		Period:    period,
		Adjust:    adjust,
		Symbol:    symbol,
		StartDate: startDate,
		EndDate:   endDate,
		Fields:    fields,
		Limit:     limit,
		Offset:    offset,
	}

	bars, err := c.Svc.QueryBars(ctx, q)
	if err != nil {
		logging.Errorf(ctx, "bars query error: %+v", err)
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}

	// Normalize trade_date
	for _, b := range bars {
		if b != nil {
			b.TradeDate = normalizeDateYYYYMMDD(b.TradeDate)
		}
	}

	// If fields are specified, trim output
	if len(fields) > 0 {
		trimmed := trimBarFields(bars, fields)
		writeJSON(w, http.StatusOK, apiResponse[any]{Data: trimmed})
		return
	}

	writeJSON(w, http.StatusOK, apiResponse[any]{Data: bars})
}

// GET /api/v2/bars/{asset_type}/{market}/last_update
func (c *BarsController) GetLastUpdate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	assetType := chi.URLParam(r, "asset_type")
	market := chi.URLParam(r, "market")
	qp := r.URL.Query()

	period := qp.Get("period")
	adjust := qp.Get("adjust")
	symbolsStr := qp.Get("symbols")

	if period == "" || adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "period and adjust are required"})
		return
	}

	var symbols []string
	if symbolsStr != "" {
		symbols = strings.Split(symbolsStr, ",")
	}
	if len(symbols) == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "symbols is required"})
		return
	}

	q := &model.BarsQuery{
		AssetType: assetType,
		Market:    market,
		Period:    period,
		Adjust:    adjust,
		Symbols:   symbols,
	}

	dates, err := c.Svc.GetLatestUpdateBySymbols(ctx, q)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, dates)
}

// trimBarFields trims StandardBar list to only include specified JSON fields.
func trimBarFields(bars []*model.StandardBar, fields []string) []map[string]any {
	fieldSet := make(map[string]struct{}, len(fields))
	for _, f := range fields {
		fieldSet[f] = struct{}{}
	}
	trimmed := make([]map[string]any, 0, len(bars))
	for _, b := range bars {
		if b == nil {
			continue
		}
		m := make(map[string]any, len(fieldSet))
		for f := range fieldSet {
			switch f {
			case "trade_date":
				m["trade_date"] = b.TradeDate
			case "symbol":
				m["symbol"] = b.Symbol
			case "open":
				m["open"] = b.Open
			case "high":
				m["high"] = b.High
			case "low":
				m["low"] = b.Low
			case "close":
				m["close"] = b.Close
			case "volume":
				m["volume"] = b.Volume
			case "amount":
				m["amount"] = b.Amount
			case "preclose":
				m["preclose"] = b.Preclose
			case "pct_chg":
				m["pct_chg"] = b.PctChg
			}
		}
		trimmed = append(trimmed, m)
	}
	return trimmed
}
