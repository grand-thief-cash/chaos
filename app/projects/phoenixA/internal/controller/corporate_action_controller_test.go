package controller

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// TestCorporateActionJSONDeserialization verifies that the JSON payload
// Artemis sends can be correctly deserialized into CorporateAction model.
func TestCorporateActionJSONDeserialization(t *testing.T) {
	// This is what Artemis sends (from base_corporate_action.py post_process,
	// Phase 3: security_id replaces symbol/market).
	artemisPayload := `[{
		"security_id": 1,
		"source": "amazing_data",
		"action_type": "dividend",
		"report_period": "20231231",
		"ann_date": "20240618",
		"progress_code": "3",
		"data_json": "{\"DVD_PER_SHARE_PRE_TAX_CASH\":27.46,\"CURRENCY_CODE\":\"CNY\"}"
	}]`

	var list []*model.CorporateAction
	err := json.Unmarshal([]byte(artemisPayload), &list)
	if err != nil {
		t.Fatalf("failed to unmarshal Artemis corporate action payload: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 record, got %d", len(list))
	}

	rec := list[0]
	assertEqual(t, "source", rec.Source, "amazing_data")
	assertEqual(t, "action_type", rec.ActionType, "dividend")
	assertEqual(t, "report_period", rec.ReportPeriod, "20231231")
	assertEqual(t, "ann_date", rec.AnnDate, "20240618")
	assertEqual(t, "progress_code", rec.ProgressCode, "3")
	if rec.SecurityID != 1 {
		t.Errorf("security_id: got %d, want 1", rec.SecurityID)
	}

	// Verify data_json is valid JSON
	var dataMap map[string]any
	// data_json from Artemis may be a double-encoded JSON string
	var raw json.RawMessage = rec.DataJSON
	var unwrapped string
	if err := json.Unmarshal(raw, &unwrapped); err == nil {
		// Double-encoded: unwrap and parse again
		raw = json.RawMessage(unwrapped)
	}
	if err := json.Unmarshal(raw, &dataMap); err != nil {
		t.Fatalf("data_json is not valid JSON: %v", err)
	}
	if dataMap["DVD_PER_SHARE_PRE_TAX_CASH"] != 27.46 {
		t.Errorf("expected DVD_PER_SHARE_PRE_TAX_CASH=27.46, got %v", dataMap["DVD_PER_SHARE_PRE_TAX_CASH"])
	}
	if dataMap["CURRENCY_CODE"] != "CNY" {
		t.Errorf("expected CURRENCY_CODE=CNY, got %v", dataMap["CURRENCY_CODE"])
	}
}

// TestCorporateActionRightIssueDeserialization verifies right_issue payload.
func TestCorporateActionRightIssueDeserialization(t *testing.T) {
	artemisPayload := `[{
		"security_id": 2,
		"source": "amazing_data",
		"action_type": "right_issue",
		"report_period": "2024",
		"ann_date": "20240115",
		"progress_code": "3",
		"data_json": "{\"PRICE\":3.12,\"RATIO\":0.18,\"COLLECTION_FUND\":1497600000.0}"
	}]`

	var list []*model.CorporateAction
	err := json.Unmarshal([]byte(artemisPayload), &list)
	if err != nil {
		t.Fatalf("failed to unmarshal right issue payload: %v", err)
	}

	rec := list[0]
	assertEqual(t, "action_type", rec.ActionType, "right_issue")
	assertEqual(t, "report_period", rec.ReportPeriod, "2024")
	assertEqual(t, "progress_code", rec.ProgressCode, "3")

	var dataMap map[string]any
	var raw json.RawMessage = rec.DataJSON
	var unwrapped string
	if err := json.Unmarshal(raw, &unwrapped); err == nil {
		raw = json.RawMessage(unwrapped)
	}
	if err := json.Unmarshal(raw, &dataMap); err != nil {
		t.Fatalf("data_json invalid: %v", err)
	}
	if dataMap["PRICE"] != 3.12 {
		t.Errorf("expected PRICE=3.12, got %v", dataMap["PRICE"])
	}
}

// TestCorporateActionFieldMapping verifies all expected fields are present
// and no unexpected fields exist in the JSON wire format.
func TestCorporateActionFieldMapping(t *testing.T) {
	expectedFields := map[string]bool{
		"security_id": true, "source": true, "action_type": true,
		"report_period": true, "ann_date": true, "progress_code": true, "data_json": true,
	}
	// Optional fields that PhoenixA adds (not from Artemis)
	optionalFields := map[string]bool{
		"id": true, "created_at": true, "updated_at": true,
	}

	rec := &model.CorporateAction{
		SecurityID:   1,
		Source:       "amazing_data",
		ActionType:   "dividend",
		ReportPeriod: "20231231",
		AnnDate:      "20240618",
		ProgressCode: "3",
		DataJSON:     json.RawMessage(`{"test":1}`),
	}

	data, err := json.Marshal(rec)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var rawMap map[string]any
	if err := json.Unmarshal(data, &rawMap); err != nil {
		t.Fatalf("unmarshal to map failed: %v", err)
	}

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

// TestCorporateActionSecurityIDParsed verifies security_id deserializes as a
// uint64 (Phase 3 replaced the symbol/market defaulting test — security_id is
// now the required identity field, no market defaulting occurs).
func TestCorporateActionSecurityIDParsed(t *testing.T) {
	payload := `[{
		"security_id": 600519,
		"report_period": "20231231",
		"ann_date": "20240618",
		"progress_code": "3",
		"data_json": "{}"
	}]`

	var list []*model.CorporateAction
	if err := json.Unmarshal([]byte(payload), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// Simulate controller logic (source/action_type enforced from URL).
	for _, item := range list {
		item.Source = "amazing_data"
		item.ActionType = "dividend"
	}

	if list[0].SecurityID != 600519 {
		t.Errorf("expected security_id=600519, got %d", list[0].SecurityID)
	}
	assertEqual(t, "source", list[0].Source, "amazing_data")
	assertEqual(t, "action_type", list[0].ActionType, "dividend")
}

// TestCorporateActionEmptyPayload tests empty array is handled.
func TestCorporateActionEmptyPayload(t *testing.T) {
	var list []*model.CorporateAction
	if err := json.Unmarshal([]byte("[]"), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(list) != 0 {
		t.Errorf("expected 0 records, got %d", len(list))
	}
}

// TestCorporateActionBatchPayload tests multi-record payload.
func TestCorporateActionBatchPayload(t *testing.T) {
	payload := `[
		{"security_id":1,"report_period":"20231231","ann_date":"20240101","progress_code":"1","data_json":"{}"},
		{"security_id":1,"report_period":"20231231","ann_date":"20240301","progress_code":"2","data_json":"{}"},
		{"security_id":1,"report_period":"20231231","ann_date":"20240618","progress_code":"3","data_json":"{}"}
	]`

	var list []*model.CorporateAction
	if err := json.Unmarshal([]byte(payload), &list); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(list) != 3 {
		t.Errorf("expected 3 records, got %d", len(list))
	}

	// Verify different progress stages for same security+period
	codes := map[string]bool{}
	for _, r := range list {
		codes[r.ProgressCode] = true
	}
	if len(codes) != 3 {
		t.Error("expected 3 different progress codes")
	}
}

// TestCorporateActionResponseSerialization verifies the JSON response format.
func TestCorporateActionResponseSerialization(t *testing.T) {
	resp := map[string]any{"status": "ok", "count": 3}
	data, err := json.Marshal(resp)
	if err != nil {
		t.Fatalf("marshal response: %v", err)
	}

	var parsed map[string]any
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if parsed["status"] != "ok" {
		t.Errorf("expected status='ok', got %v", parsed["status"])
	}
	if parsed["count"] != float64(3) {
		t.Errorf("expected count=3, got %v", parsed["count"])
	}
}

// TestWriteJSON verifies the writeJSON utility function.
func TestWriteJSON(t *testing.T) {
	w := httptest.NewRecorder()
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": 5})

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type=application/json, got %s", ct)
	}

	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("response body not valid JSON: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("expected status=ok, got %v", body["status"])
	}
}

// TestWriteJSONError verifies error response.
func TestWriteJSONError(t *testing.T) {
	w := httptest.NewRecorder()
	writeJSON(w, http.StatusBadRequest, apiError{Error: "test error"})

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("response body not valid JSON: %v", err)
	}
	if body["error"] != "test error" {
		t.Errorf("expected error='test error', got %v", body["error"])
	}
}

// TestCorporateActionDataJSONIntegrity tests that data_json round-trips correctly.
func TestCorporateActionDataJSONIntegrity(t *testing.T) {
	// Simulate a complex data_json from Artemis
	originalData := map[string]any{
		"DVD_PER_SHARE_PRE_TAX_CASH":   27.46,
		"DVD_PER_SHARE_AFTER_TAX_CASH": 24.714,
		"DATE_EQY_RECORD":              "20240618",
		"DATE_EX":                      "20240619",
		"CURRENCY_CODE":                "CNY",
		"DIV_BASESHARE":                125619.78,
		"IS_CHANGED":                   0,
		"DIV_BONUSRATE":                0.0,
	}

	dataBytes, _ := json.Marshal(originalData)
	dataStr := json.RawMessage(dataBytes)

	// Put into model
	rec := &model.CorporateAction{
		SecurityID:   1,
		Source:       "amazing_data",
		ActionType:   "dividend",
		ReportPeriod: "20231231",
		AnnDate:      "20240618",
		ProgressCode: "3",
		DataJSON:     dataStr,
	}

	// Serialize to JSON (as would happen in HTTP response)
	wireBytes, err := json.Marshal(rec)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	// Deserialize back
	var decoded model.CorporateAction
	if err := json.Unmarshal(wireBytes, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// Parse data_json and verify values
	var parsedData map[string]any
	if err := json.Unmarshal([]byte(decoded.DataJSON), &parsedData); err != nil {
		t.Fatalf("data_json parse: %v", err)
	}

	if parsedData["DVD_PER_SHARE_PRE_TAX_CASH"] != 27.46 {
		t.Errorf("DVD_PER_SHARE_PRE_TAX_CASH mismatch")
	}
	if parsedData["CURRENCY_CODE"] != "CNY" {
		t.Errorf("CURRENCY_CODE mismatch")
	}
	if parsedData["DIV_BASESHARE"] != 125619.78 {
		t.Errorf("DIV_BASESHARE mismatch")
	}
}

// TestInvalidJSONBody verifies error handling for malformed JSON.
func TestInvalidJSONBody(t *testing.T) {
	body := bytes.NewBufferString("{invalid json")
	var list []*model.CorporateAction
	err := json.NewDecoder(body).Decode(&list)
	if err == nil {
		t.Error("expected error for invalid JSON, got nil")
	}
}

func assertEqual(t *testing.T, field, got, want string) {
	t.Helper()
	if got != want {
		t.Errorf("%s: got %q, want %q", field, got, want)
	}
}
