package controller

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestFinancialStatementJSONDeserialization verifies Artemis payload can be
// correctly deserialized into FinancialStatement model.
func TestFinancialStatementJSONDeserialization(t *testing.T) {
	// Exact payload format from Artemis base_financial_statement.py (Phase 3:
	// security_id replaces symbol/market).
	artemisPayload := `[{
		"security_id": 1,
		"source": "amazing_data",
		"statement_type": "balance_sheet",
		"reporting_period": "20231231",
		"report_type": "4",
		"statement_code": "1",
		"security_name": "平安银行",
		"ann_date": "20240320",
		"actual_ann_date": "20240320",
		"comp_type_code": 2,
		"data_json": "{\"TOTAL_ASSETS\":5600000000000.0,\"TOTAL_LIAB\":5100000000000.0}"
	}]`

	var list []*model.FinancialStatement
	err := json.Unmarshal([]byte(artemisPayload), &list)
	if err != nil {
		t.Fatalf("failed to unmarshal Artemis financial statement payload: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 record, got %d", len(list))
	}

	rec := list[0]
	cases := []struct{ field, got, want string }{
		{"source", rec.Source, "amazing_data"},
		{"statement_type", rec.StatementType, "balance_sheet"},
		{"reporting_period", rec.ReportingPeriod, "20231231"},
		{"report_type", rec.ReportType, "4"},
		{"statement_code", rec.StatementCode, "1"},
		{"security_name", rec.SecurityName, "平安银行"},
		{"ann_date", rec.AnnDate, "20240320"},
		{"actual_ann_date", rec.ActualAnnDate, "20240320"},
	}
	for _, c := range cases {
		if c.got != c.want {
			t.Errorf("%s: got %q, want %q", c.field, c.got, c.want)
		}
	}
	if rec.SecurityID != 1 {
		t.Errorf("security_id: got %d, want 1", rec.SecurityID)
	}
	if rec.CompTypeCode != 2 {
		t.Errorf("comp_type_code: got %d, want 2", rec.CompTypeCode)
	}

	// Verify data_json
	var dataMap map[string]any
	var raw json.RawMessage = rec.DataJSON
	var unwrapped string
	if err := json.Unmarshal(raw, &unwrapped); err == nil {
		raw = json.RawMessage(unwrapped)
	}
	if err := json.Unmarshal(raw, &dataMap); err != nil {
		t.Fatalf("data_json not valid JSON: %v", err)
	}
	if dataMap["TOTAL_ASSETS"] != 5600000000000.0 {
		t.Errorf("TOTAL_ASSETS: got %v, want 5600000000000", dataMap["TOTAL_ASSETS"])
	}
}

// TestFinancialStatementFieldMapping verifies all JSON tags match Artemis output.
func TestFinancialStatementFieldMapping(t *testing.T) {
	expectedFields := map[string]bool{
		"security_id": true, "source": true, "statement_type": true,
		"reporting_period": true, "report_type": true, "statement_code": true,
		"security_name": true, "ann_date": true, "actual_ann_date": true,
		"comp_type_code": true, "data_json": true,
	}
	optionalFields := map[string]bool{
		"id": true, "created_at": true, "updated_at": true,
	}

	rec := &model.FinancialStatement{
		SecurityID:      1,
		Source:          "amazing_data",
		StatementType:   "balance_sheet",
		ReportingPeriod: "20231231",
		ReportType:      "4",
		StatementCode:   "1",
		SecurityName:    "平安银行",
		AnnDate:         "20240320",
		ActualAnnDate:   "20240320",
		CompTypeCode:    2,
		DataJSON:        json.RawMessage(`{"TOTAL_ASSETS":1}`),
	}

	data, _ := json.Marshal(rec)
	var rawMap map[string]any
	json.Unmarshal(data, &rawMap)

	for field := range expectedFields {
		if _, ok := rawMap[field]; !ok {
			t.Errorf("missing expected field: %s", field)
		}
	}
	for field := range rawMap {
		if !expectedFields[field] && !optionalFields[field] {
			t.Errorf("unexpected field in JSON: %s", field)
		}
	}
}

// TestFinancialStatementProfitExpressNoMetadata
// profit_express sends empty strings for report_type, statement_code, security_name.
func TestFinancialStatementProfitExpressNoMetadata(t *testing.T) {
	payload := `[{
		"security_id": 1,
		"source": "amazing_data",
		"statement_type": "profit_express",
		"reporting_period": "20231231",
		"report_type": "",
		"statement_code": "",
		"security_name": "",
		"ann_date": "20240115",
		"actual_ann_date": "20240115",
		"comp_type_code": 0,
		"data_json": "{\"TOTAL_ASSETS\":5600000000000.0,\"EPS_BASIC\":2.37}"
	}]`

	var list []*model.FinancialStatement
	if err := json.Unmarshal([]byte(payload), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	rec := list[0]
	if rec.ReportType != "" {
		t.Errorf("report_type should be empty for profit_express, got %q", rec.ReportType)
	}
	if rec.StatementCode != "" {
		t.Errorf("statement_code should be empty for profit_express, got %q", rec.StatementCode)
	}
	if rec.CompTypeCode != 0 {
		t.Errorf("comp_type_code should be 0 for profit_express, got %d", rec.CompTypeCode)
	}
}

// TestFinancialStatementSecurityIDParsed verifies security_id deserializes as a
// uint64 (Phase 3 replaced the symbol/market defaulting test — security_id is
// now the required identity field, no market defaulting occurs).
func TestFinancialStatementSecurityIDParsed(t *testing.T) {
	payload := `[{
		"security_id": 600519,
		"reporting_period": "20231231",
		"data_json": "{}"
	}]`

	var list []*model.FinancialStatement
	if err := json.Unmarshal([]byte(payload), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if list[0].SecurityID != 600519 {
		t.Errorf("expected security_id=600519, got %d", list[0].SecurityID)
	}
}

// TestQueryRejectsMalformedIdentityParam is a handler-level test ensuring a
// present-but-empty/invalid security_id or security_ids param returns 400
// (never silently degrades to an unfiltered query). Uses q.Has, so ?security_id=
// (empty value, distinct from param-absent) is treated as supplied-but-invalid.
// The 400 returns before the service is touched, so a nil Svc is safe.
func TestQueryRejectsMalformedIdentityParam(t *testing.T) {
	cases := []string{
		"?security_id=",      // empty value → 400 (not unfiltered)
		"?security_ids=",     // empty value → 400
		"?security_id=0",     // zero → 400
		"?security_ids=1,,2", // consecutive comma → 400
		"?security_ids=abc",  // non-numeric → 400
		"?security_ids=,",    // only commas → 400
	}
	for _, qs := range cases {
		c := &FinancialStatementController{} // Svc nil — 400 returns before service call
		req := httptest.NewRequest(http.MethodGet, "/api/v2/financial/amazing_data/balance_sheet"+qs, nil)
		w := httptest.NewRecorder()
		c.Query(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("query %q: got status %d, want 400", qs, w.Code)
		}
	}
}

// TestParseUint64ListStrict locks in the strict security_ids parsing contract:
// a non-numeric, zero, or empty token (leading/trailing/consecutive comma, or
// whitespace-only) must error (→ 400), never silently degrade to an unfiltered
// query. Whitespace around tokens is tolerated.
func TestParseUint64ListStrict(t *testing.T) {
	cases := []struct {
		in      string
		want    []uint64
		wantErr bool
	}{
		{"1,2,3", []uint64{1, 2, 3}, false},
		{"1,2,1", []uint64{1, 2}, false},   // dedup
		{" 1 , 2 ", []uint64{1, 2}, false}, // whitespace around tokens tolerated
		{"1,,2", nil, true},                // consecutive comma → error
		{"1,2,", nil, true},                // trailing comma → error
		{",", nil, true},                   // only commas → error
		{" ", nil, true},                   // whitespace-only → error
		{"", nil, true},                    // empty → error
		{"abc", nil, true},                 // non-numeric → error
		{"1,abc", nil, true},               // partial invalid → error
		{"0", nil, true},                   // zero → error
		{"1,0", nil, true},                 // zero in list → error
	}
	for _, c := range cases {
		got, err := parseUint64ListStrict(c.in)
		if c.wantErr {
			if err == nil {
				t.Errorf("parseUint64ListStrict(%q): want error, got %v", c.in, got)
			}
			continue
		}
		if err != nil {
			t.Errorf("parseUint64ListStrict(%q): unexpected err: %v", c.in, err)
			continue
		}
		if len(got) != len(c.want) {
			t.Errorf("parseUint64ListStrict(%q): got %v, want %v", c.in, got, c.want)
			continue
		}
		for i := range got {
			if got[i] != c.want[i] {
				t.Errorf("parseUint64ListStrict(%q): got %v, want %v", c.in, got, c.want)
			}
		}
	}
}
func TestFinancialStatementDataJSONRoundTrip(t *testing.T) {
	original := map[string]any{
		"TOTAL_ASSETS":  5600000000000.0,
		"TOTAL_LIAB":    5100000000000.0,
		"CAP_STOCK":     19405918198.0,
		"GOODWILL":      0.0,
		"CURRENCY_CODE": "CNY",
	}

	dataBytes, _ := json.Marshal(original)
	rec := &model.FinancialStatement{
		SecurityID:      1,
		Source:          "amazing_data",
		StatementType:   "balance_sheet",
		ReportingPeriod: "20231231",
		DataJSON:        json.RawMessage(dataBytes),
	}

	wireBytes, _ := json.Marshal(rec)

	var decoded model.FinancialStatement
	json.Unmarshal(wireBytes, &decoded)

	var parsed map[string]any
	if err := json.Unmarshal([]byte(decoded.DataJSON), &parsed); err != nil {
		t.Fatalf("data_json parse: %v", err)
	}

	if parsed["TOTAL_ASSETS"] != 5600000000000.0 {
		t.Errorf("TOTAL_ASSETS roundtrip failed: %v", parsed["TOTAL_ASSETS"])
	}
	if parsed["CURRENCY_CODE"] != "CNY" {
		t.Errorf("CURRENCY_CODE roundtrip failed: %v", parsed["CURRENCY_CODE"])
	}
}
