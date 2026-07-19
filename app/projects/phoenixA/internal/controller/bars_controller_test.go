package controller

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestBarsUpsertPayloadDeserialization verifies the Phase 4 artemis upsert
// payload (security_id-native, no symbol) deserializes into the input rows.
// bars_* physical tables keep symbol (§3.2), so the input row carries
// security_id which the controller resolves to symbol before the DAO.
func TestBarsUpsertPayloadDeserialization(t *testing.T) {
	payload := `{
		"meta": {"period": "daily", "adjust": "nf", "source": "baostock"},
		"bars": [{
			"security_id": 1,
			"trade_date": "2026-01-05",
			"open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5,
			"volume": 1000, "amount": 10500,
			"preclose": 9.8, "pct_chg": 1.92
		}],
		"ext": [{
			"security_id": 1,
			"trade_date": "2026-01-05",
			"turn": 1.2, "pe_ttm": 15.0, "ps_ttm": 2.0, "pb_mrq": 1.5, "pcf_ncf_ttm": 8.0
		}]
	}`

	var req model.BarsUpsertRequest
	if err := json.Unmarshal([]byte(payload), &req); err != nil {
		t.Fatalf("unmarshal request: %v", err)
	}
	var bars []barInputRow
	if err := json.Unmarshal(req.Bars, &bars); err != nil {
		t.Fatalf("unmarshal bars: %v", err)
	}
	if len(bars) != 1 || bars[0].SecurityID != 1 {
		t.Fatalf("expected 1 bar with security_id=1, got %+v", bars)
	}
	if bars[0].Open != 10.0 || bars[0].PctChg != 1.92 {
		t.Errorf("bar fields misparsed: %+v", bars[0])
	}

	var ext []barExtInputRow
	if err := json.Unmarshal(req.Ext, &ext); err != nil {
		t.Fatalf("unmarshal ext: %v", err)
	}
	if len(ext) != 1 || ext[0].SecurityID != 1 {
		t.Fatalf("expected 1 ext row with security_id=1, got %+v", ext)
	}
	if ext[0].PeTTM != 15.0 || ext[0].PbMRQ != 1.5 {
		t.Errorf("ext fields misparsed: %+v", ext[0])
	}
}

// TestStandardBarSecurityIDDecoration verifies SecurityID is a response-only
// decoration: it has gorm:"-" (not a physical column, §3.2) and serializes as
// "security_id", omitted when zero.
func TestStandardBarSecurityIDDecoration(t *testing.T) {
	b := &model.StandardBar{SecurityID: 7, Symbol: "000001", TradeDate: "2026-01-05", Close: 10.5}
	data, _ := json.Marshal(b)
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if m["security_id"] != float64(7) {
		t.Errorf("security_id: got %v, want 7", m["security_id"])
	}
	if m["symbol"] != "000001" {
		t.Errorf("symbol: got %v, want 000001", m["symbol"])
	}

	// Zero security_id is omitted (omitempty), matching the physical-row shape
	// used on the write path where security_id is not yet stamped.
	bZero := &model.StandardBar{Symbol: "000001", TradeDate: "2026-01-05"}
	dataZero, _ := json.Marshal(bZero)
	var mZero map[string]any
	json.Unmarshal(dataZero, &mZero)
	if _, ok := mZero["security_id"]; ok {
		t.Errorf("zero security_id should be omitted, got %v", mZero["security_id"])
	}
}

// TestBarsQueryRejectsMalformedIdentityParam is a handler-level test ensuring a
// present-but-empty/invalid security_id returns 400 (never silently degrades),
// and that the deprecated symbol/symbols params are rejected (no dual-track,
// §3.6). The 400 returns before the service/resolve cache is touched, so nil
// deps are safe.
func TestBarsQueryRejectsMalformedIdentityParam(t *testing.T) {
	cases := []string{
		"",                                     // no identity → 400 required
		"?security_id=",                        // empty → 400
		"?security_id=0",                       // zero → 400
		"?security_id=abc",                     // non-numeric → 400
		"?security_id=-1",                      // negative → 400
		"?symbol=000001",                       // deprecated → 400
		"?symbols=000001,000002",               // deprecated → 400
		"?security_id=1&symbol=000001",         // deprecated symbol alongside valid id → 400 (no silent ignore)
		"?security_id=1&symbols=000001,000002", // deprecated symbols alongside valid id → 400
		"?security_id=1&start_date=2026-01-01", // missing end_date/period/adjust → 400
	}
	for _, qs := range cases {
		c := &BarsController{} // Svc/ResolveCache nil — 400 returns before they're touched
		req := httptest.NewRequest(http.MethodGet, "/api/v2/bars/stock/zh_a"+qs, nil)
		w := httptest.NewRecorder()
		c.Query(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("query %q: got status %d, want 400", qs, w.Code)
		}
	}
}

// TestBarsGetLastUpdateRejectsMalformedIdentityParam verifies last_update strict
// security_ids parsing + deprecated symbols rejection. period/adjust are
// supplied so the 400 comes from the identity check, not the required-param
// check.
func TestBarsGetLastUpdateRejectsMalformedIdentityParam(t *testing.T) {
	base := "?period=daily&adjust=nf"
	cases := []string{
		base,                                   // no identity → 400 required
		base + "&security_ids=",                // empty → 400
		base + "&security_ids=1,,2",            // consecutive comma → 400
		base + "&security_ids=abc",             // non-numeric → 400
		base + "&security_ids=0",               // zero → 400
		base + "&security_ids=1,0",             // zero in list → 400
		base + "&security_id=0",                // single zero → 400
		base + "&security_id=abc",              // single non-numeric → 400
		base + "&symbols=000001",               // deprecated → 400
		base + "&security_id=1&symbols=000001", // deprecated symbols alongside valid id → 400 (no silent ignore)
	}
	for _, qs := range cases {
		c := &BarsController{}
		req := httptest.NewRequest(http.MethodGet, "/api/v2/bars/stock/zh_a/last_update"+qs, nil)
		w := httptest.NewRecorder()
		c.GetLastUpdate(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("last_update %q: got status %d, want 400", qs, w.Code)
		}
	}
}

// TestBarsGetLastUpdateMissingPeriodAdjust verifies the required-param check
// fires before the identity check.
func TestBarsGetLastUpdateMissingPeriodAdjust(t *testing.T) {
	c := &BarsController{}
	req := httptest.NewRequest(http.MethodGet, "/api/v2/bars/stock/zh_a/last_update?security_ids=1", nil)
	w := httptest.NewRecorder()
	c.GetLastUpdate(w, req)
	if w.Code != http.StatusBadRequest {
		t.Errorf("got status %d, want 400 for missing period/adjust", w.Code)
	}
}

// TestTrimBarFieldsSelectsSecurityID verifies fields=security_id,symbol,close
// returns exactly those fields, with security_id read from the stamped decoration.
func TestTrimBarFieldsSelectsSecurityID(t *testing.T) {
	bars := []*model.StandardBar{
		{SecurityID: 7, Symbol: "000001", TradeDate: "2026-01-05", Close: 10.5, Open: 10.0},
	}
	trimmed := trimBarFields(bars, []string{"security_id", "symbol", "close"})
	if len(trimmed) != 1 {
		t.Fatalf("expected 1 row, got %d", len(trimmed))
	}
	m := trimmed[0]
	if len(m) != 3 {
		t.Errorf("expected 3 fields, got %d (%+v)", len(m), m)
	}
	if m["security_id"] != uint64(7) {
		t.Errorf("security_id: got %v, want 7", m["security_id"])
	}
	if m["symbol"] != "000001" {
		t.Errorf("symbol: got %v, want 000001", m["symbol"])
	}
	if m["close"] != 10.5 {
		t.Errorf("close: got %v, want 10.5", m["close"])
	}
}
