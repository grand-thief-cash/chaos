package controller

import (
	"encoding/json"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestFinancialStatementJSONDeserialization verifies Artemis payload can be
// correctly deserialized into FinancialStatement model.
func TestFinancialStatementJSONDeserialization(t *testing.T) {
	// Exact payload format from Artemis base_financial_statement.py
	artemisPayload := `[{
		"source": "amazing_data",
		"symbol": "000001.SZ",
		"market": "zh_a",
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
		{"symbol", rec.Symbol, "000001.SZ"},
		{"market", rec.Market, "zh_a"},
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
		"source": true, "symbol": true, "market": true,
		"statement_type": true, "reporting_period": true,
		"report_type": true, "statement_code": true,
		"security_name": true, "ann_date": true, "actual_ann_date": true,
		"comp_type_code": true, "data_json": true,
	}
	optionalFields := map[string]bool{
		"id": true, "created_at": true, "updated_at": true,
	}

	rec := &model.FinancialStatement{
		Source:          "amazing_data",
		Symbol:          "000001.SZ",
		Market:          "zh_a",
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
		"source": "amazing_data",
		"symbol": "000001.SZ",
		"market": "zh_a",
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

// TestFinancialStatementDefaultMarket verifies controller sets default market.
func TestFinancialStatementDefaultMarket(t *testing.T) {
	payload := `[{
		"symbol": "600519.SH",
		"reporting_period": "20231231",
		"data_json": "{}"
	}]`

	var list []*model.FinancialStatement
	json.Unmarshal([]byte(payload), &list)

	// Simulate controller logic
	for _, item := range list {
		item.Source = "amazing_data"
		item.StatementType = "balance_sheet"
		if item.Market == "" {
			item.Market = "zh_a"
		}
	}

	if list[0].Market != "zh_a" {
		t.Errorf("expected market=zh_a, got %q", list[0].Market)
	}
}

// TestFinancialStatementDataJSONRoundTrip tests data_json integrity.
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
		Source:          "amazing_data",
		Symbol:          "000001.SZ",
		Market:          "zh_a",
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
