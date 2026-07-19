package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
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
//
// Phase 4: the API contract is security_id-native (no dual-track, refactor
// §3.6). security_id is resolved to the physical symbol at the controller
// boundary; bars_* tables keep symbol as their physical primary key (§3.2
// permanent-storage exception). Path {asset_type}/{market} is validated
// against the resolved security and returns 400 on mismatch (§10.d.4 option A).
// symbol/symbols params are rejected (deprecated) — callers must use security_id.
type BarsController struct {
	*core.BaseComponent
	Svc          *service.BarsService       `infra:"dep:svc_bars"`
	BufferMgr    *buffer.WriteBufferManager `infra:"dep:write_buffer_mgr"`
	ResolveCache *service.ResolveCache      `infra:"dep:svc_resolve_cache"`
}

func NewBarsController() *BarsController {
	return &BarsController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_BARS)}
}

func (c *BarsController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *BarsController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

// barInputRow is the API input shape for a standard bar row: identity is
// security_id (resolved to symbol before reaching the DAO/write buffer). It is
// distinct from model.StandardBar, which is the physical row (symbol-keyed, no
// security_id column, §3.2).
type barInputRow struct {
	SecurityID uint64  `json:"security_id"`
	TradeDate  string  `json:"trade_date"`
	Open       float64 `json:"open"`
	High       float64 `json:"high"`
	Low        float64 `json:"low"`
	Close      float64 `json:"close"`
	Volume     int64   `json:"volume"`
	Amount     int64   `json:"amount"`
	Preclose   float64 `json:"preclose,omitempty"`
	PctChg     float64 `json:"pct_chg,omitempty"`
}

// barExtInputRow is the API input shape for a bars extension row.
type barExtInputRow struct {
	SecurityID uint64  `json:"security_id"`
	TradeDate  string  `json:"trade_date"`
	Turn       float64 `json:"turn,omitempty"`
	PeTTM      float64 `json:"pe_ttm,omitempty"`
	PsTTM      float64 `json:"ps_ttm,omitempty"`
	PbMRQ      float64 `json:"pb_mrq,omitempty"`
	PcfNcfTTM  float64 `json:"pcf_ncf_ttm,omitempty"`
}

// POST /api/v2/bars/{asset_type}/{market}/upsert
//
// Request body: {meta:{period,adjust,source}, bars:[{security_id,...}], ext:[{security_id,...}]}.
// Each bar/ext row MUST carry a security_id resolved from security_registry;
// unknown id or path/{asset_type,market} mismatch → 400 (orphan defense, §10.c).
// The controller resolves security_id → symbol before the DAO/write buffer, so
// the physical rows entering the async buffer are already validated (§10.d.2).
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

	var inputBars []barInputRow
	if err := json.Unmarshal(req.Bars, &inputBars); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("bars parse error: %s", err.Error())})
		return
	}
	var inputExt []barExtInputRow
	if len(req.Ext) > 0 {
		if err := json.Unmarshal(req.Ext, &inputExt); err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: fmt.Sprintf("ext parse error: %s", err.Error())})
			return
		}
	}

	// Collect security_ids; every row must carry a positive one.
	ids := make([]uint64, 0, len(inputBars)+len(inputExt))
	for _, b := range inputBars {
		if b.SecurityID == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id is required in each bar"})
			return
		}
		ids = append(ids, b.SecurityID)
	}
	for _, e := range inputExt {
		if e.SecurityID == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id is required in each ext row"})
			return
		}
		ids = append(ids, e.SecurityID)
	}

	// Resolve each unique id → symbol, validating existence + path asset_type/market.
	// The resolve IS the orphan defense (found=false = orphan, §10.c); a cache/DB
	// load failure surfaces as 500 (not the caller's fault).
	symbolByID, err := c.resolveSymbolsForPath(ctx, ids, assetType, market)
	if err != nil {
		writeServiceError(w, err)
		return
	}

	// Build resolved physical rows.
	bars := make([]*model.StandardBar, 0, len(inputBars))
	for _, ib := range inputBars {
		bars = append(bars, &model.StandardBar{
			Symbol:    symbolByID[ib.SecurityID],
			TradeDate: ib.TradeDate,
			Open:      ib.Open,
			High:      ib.High,
			Low:       ib.Low,
			Close:     ib.Close,
			Volume:    ib.Volume,
			Amount:    ib.Amount,
			Preclose:  ib.Preclose,
			PctChg:    ib.PctChg,
		})
	}
	ext := make([]*model.BarsExtBaostock, 0, len(inputExt))
	for _, ie := range inputExt {
		ext = append(ext, &model.BarsExtBaostock{
			Symbol:    symbolByID[ie.SecurityID],
			TradeDate: ie.TradeDate,
			Turn:      ie.Turn,
			PeTTM:     ie.PeTTM,
			PsTTM:     ie.PsTTM,
			PbMRQ:     ie.PbMRQ,
			PcfNcfTTM: ie.PcfNcfTTM,
		})
	}

	q := &model.BarsQuery{
		AssetType: assetType,
		Market:    market,
		Period:    req.Meta.Period,
		Adjust:    req.Meta.Adjust,
	}

	// ── Write Buffer routing ──
	if c.BufferMgr != nil && c.BufferMgr.IsEnabled() {
		if len(bars) >= c.BufferMgr.DirectFlushThreshold() {
			// Large batch: direct write.
			if err := c.Svc.Dao.BatchUpsert(ctx, q, bars); err != nil {
				errMsg := fmt.Sprintf("bars upsert error: %s", err.Error())
				logging.Error(ctx, errMsg)
				writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
				return
			}
			if len(ext) > 0 && req.Meta.Source != "" {
				if err := c.Svc.BatchUpsertExt(ctx, req.Meta.Source, q, ext); err != nil {
					logging.Errorf(ctx, "bars ext upsert error: %s", err.Error())
				}
			}
		} else {
			// Small batch: submit to write buffer. The buffer's Submit takes ext
			// as json.RawMessage (it stores bytes for async flush), so marshal ext
			// only on this path; bars pass through as structs.
			var extJSON json.RawMessage
			if len(ext) > 0 {
				extJSON, _ = json.Marshal(ext)
			}
			if err := c.BufferMgr.Submit(q, bars, extJSON, req.Meta.Source); err != nil {
				logging.Errorf(ctx, "write buffer submit failed: %s", err.Error())
				writeJSON(w, http.StatusServiceUnavailable, apiError{Error: "write buffer full, retry later"})
				return
			}
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}

	// ── Direct path (buffer disabled or nil) ──
	if err := c.Svc.BatchUpsert(ctx, q, bars); err != nil {
		errMsg := fmt.Sprintf("bars upsert error: %s", err.Error())
		logging.Error(ctx, errMsg)
		writeJSON(w, http.StatusBadRequest, apiError{Error: errMsg})
		return
	}
	if len(ext) > 0 && req.Meta.Source != "" {
		if err := c.Svc.BatchUpsertExt(ctx, req.Meta.Source, q, ext); err != nil {
			logging.Errorf(ctx, "bars ext upsert error: %s", err.Error())
		}
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// resolveSymbolsForPath resolves each id to its security, validates that the
// path {asset_type}/{market} matches the resolved security, and returns id→symbol.
// Dedupes ids. A genuine miss or path mismatch is a ValidationError (→400); a
// cache/DB load failure is a plain error (→500).
func (c *BarsController) resolveSymbolsForPath(ctx context.Context, ids []uint64, assetType, market string) (map[uint64]string, error) {
	symbolByID := make(map[uint64]string, len(ids))
	for _, id := range ids {
		if _, ok := symbolByID[id]; ok {
			continue
		}
		sec, found, err := c.ResolveCache.ResolveSecurity(ctx, id)
		if err != nil {
			return nil, err
		}
		if !found {
			return nil, service.NewValidationError("security_id %d does not exist in security_registry", id)
		}
		if sec.AssetType != assetType {
			return nil, service.NewValidationError("asset_type mismatch for security_id %d: path=%s, registry=%s", id, assetType, sec.AssetType)
		}
		if sec.Market != market {
			return nil, service.NewValidationError("market mismatch for security_id %d: path=%s, registry=%s", id, market, sec.Market)
		}
		symbolByID[id] = sec.Symbol
	}
	return symbolByID, nil
}

// GET /api/v2/bars/{asset_type}/{market}
//
// Query params: security_id (required), period (required), adjust (required),
// start_date/end_date (required), fields (optional), limit/offset (optional).
// symbol/symbols are rejected (deprecated) — no dual-track (§3.6).
func (c *BarsController) Query(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	assetType := chi.URLParam(r, "asset_type")
	market := chi.URLParam(r, "market")
	qp := r.URL.Query()

	// symbol/symbols are deprecated (no dual-track, §3.6) — reject whenever
	// present, even if security_id is also supplied (a stale client passing
	// both must not silently ignore the deprecated params).
	if qp.Has("symbol") || qp.Has("symbols") {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "symbol/symbols parameters are deprecated; use security_id"})
		return
	}
	// Strict security_id presence + parsing (Phase 1/3 pattern: q.Has distinguishes
	// absent from present-but-empty; present-but-empty/zero/non-numeric → 400).
	var securityID uint64
	if !qp.Has("security_id") {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id is required"})
		return
	}
	id, err := strconv.ParseUint(strings.TrimSpace(qp.Get("security_id")), 10, 64)
	if err != nil || id == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id: must be a positive integer"})
		return
	}
	securityID = id

	startDate := strings.TrimSpace(qp.Get("start_date"))
	endDate := strings.TrimSpace(qp.Get("end_date"))
	period := strings.TrimSpace(qp.Get("period"))
	adjust := strings.TrimSpace(qp.Get("adjust"))
	limit, offset := parseLimitOffset(r)
	fields := parseFieldsParam(qp.Get("fields"))

	if startDate == "" || endDate == "" || period == "" || adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id, start_date, end_date, period, adjust are required"})
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

	// Resolve security_id → symbol, validating path asset_type/market (§10.d.4 option A).
	symbolByID, err := c.resolveSymbolsForPath(ctx, []uint64{securityID}, assetType, market)
	if err != nil {
		writeServiceError(w, err)
		return
	}

	q := &model.BarsQuery{
		AssetType: assetType,
		Market:    market,
		Period:    period,
		Adjust:    adjust,
		Symbol:    symbolByID[securityID],
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

	// Normalize trade_date and stamp security_id onto each row for the response
	// (physical table has no security_id column; it's a decoration, §10.b).
	for _, b := range bars {
		if b == nil {
			continue
		}
		b.TradeDate = normalizeDateYYYYMMDD(b.TradeDate)
		b.SecurityID = securityID
	}

	if len(fields) > 0 {
		writeJSON(w, http.StatusOK, apiResponse[any]{Data: trimBarFields(bars, fields)})
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: bars})
}

// GET /api/v2/bars/{asset_type}/{market}/last_update
//
// Query params: security_id (single) or security_ids (comma-separated, required),
// period (required), adjust (required). symbols is rejected (deprecated). Returns
// the last trade date per security as [{security_id, symbol, last_update}].
// Accepting both security_id and security_ids matches the other data-table
// endpoints and the artemis convenience layer (which collapses a single id to
// security_id).
func (c *BarsController) GetLastUpdate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	assetType := chi.URLParam(r, "asset_type")
	market := chi.URLParam(r, "market")
	qp := r.URL.Query()

	period := strings.TrimSpace(qp.Get("period"))
	adjust := strings.TrimSpace(qp.Get("adjust"))
	if period == "" || adjust == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "period and adjust are required"})
		return
	}

	// symbol/symbols are deprecated (no dual-track, §3.6) — reject whenever present.
	if qp.Has("symbol") || qp.Has("symbols") {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "symbol/symbols parameters are deprecated; use security_id/security_ids"})
		return
	}

	// Collect ids from security_id (single) and/or security_ids (list).
	var securityIDs []uint64
	if qp.Has("security_id") {
		id, err := strconv.ParseUint(strings.TrimSpace(qp.Get("security_id")), 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id: must be a positive integer"})
			return
		}
		securityIDs = append(securityIDs, id)
	}
	if qp.Has("security_ids") {
		ids, err := parseUint64ListStrict(qp.Get("security_ids"))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
			return
		}
		securityIDs = append(securityIDs, ids...)
	}
	if len(securityIDs) == 0 {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "security_id or security_ids is required"})
		return
	}
	// Dedupe while preserving order.
	seen := make(map[uint64]struct{}, len(securityIDs))
	deduped := make([]uint64, 0, len(securityIDs))
	for _, id := range securityIDs {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		deduped = append(deduped, id)
	}
	securityIDs = deduped

	// Resolve each id → symbol, validating path asset_type/market.
	symbolByID, err := c.resolveSymbolsForPath(ctx, securityIDs, assetType, market)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	symbols := make([]string, 0, len(securityIDs))
	for _, id := range securityIDs {
		symbols = append(symbols, symbolByID[id])
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

	// Transform symbol-keyed dates → [{security_id, symbol, last_update}],
	// preserving the caller's security_ids order.
	result := make([]map[string]any, 0, len(securityIDs))
	for _, id := range securityIDs {
		symbol := symbolByID[id]
		date, ok := dates[symbol]
		if !ok {
			continue
		}
		result = append(result, map[string]any{
			"security_id": id,
			"symbol":      symbol,
			"last_update": date,
		})
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: result})
}

// trimBarFields trims StandardBar list to only include specified JSON fields.
// security_id is selectable and reads from the stamped response decoration.
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
			case "security_id":
				m["security_id"] = b.SecurityID
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
