package model

import (
	"encoding/json"
	"testing"
)

func TestFinancialStatementTableName(t *testing.T) {
	m := FinancialStatement{}
	if m.TableName() != "ods.financial_statement" {
		t.Errorf("expected table name 'ods.financial_statement', got %q", m.TableName())
	}
}

func TestCorporateActionTableName(t *testing.T) {
	m := CorporateAction{}
	if m.TableName() != "ods.corporate_action" {
		t.Errorf("expected table name 'ods.corporate_action', got %q", m.TableName())
	}
}

func TestFinancialStatementJSONTags(t *testing.T) {
	rec := FinancialStatement{
		Source:          "src",
		Symbol:          "sym",
		Market:          "mkt",
		StatementType:   "st",
		ReportingPeriod: "rp",
		ReportType:      "rt",
		StatementCode:   "sc",
		SecurityName:    "sn",
		AnnDate:         "ad",
		ActualAnnDate:   "aad",
		CompTypeCode:    1,
		DataJSON:        json.RawMessage(`{"k":"v"}`),
	}

	data, err := json.Marshal(rec)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var m map[string]any
	json.Unmarshal(data, &m)

	required := []string{
		"source", "symbol", "market", "statement_type",
		"reporting_period", "report_type", "statement_code",
		"security_name", "ann_date", "actual_ann_date",
		"comp_type_code", "data_json",
	}
	for _, f := range required {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}
}

func TestCorporateActionJSONTags(t *testing.T) {
	rec := CorporateAction{
		Source:       "src",
		Symbol:       "sym",
		Market:       "mkt",
		ActionType:   "at",
		ReportPeriod: "rp",
		AnnDate:      "ad",
		ProgressCode: "pc",
		DataJSON:     json.RawMessage(`{"k":"v"}`),
	}

	data, err := json.Marshal(rec)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var m map[string]any
	json.Unmarshal(data, &m)

	required := []string{
		"source", "symbol", "market", "action_type",
		"report_period", "ann_date", "progress_code", "data_json",
	}
	for _, f := range required {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}
}

// TestCompTypeCodeIsInt verifies comp_type_code serializes as integer, not string.
func TestCompTypeCodeIsInt(t *testing.T) {
	rec := FinancialStatement{CompTypeCode: 2, DataJSON: json.RawMessage("{}")}
	data, _ := json.Marshal(rec)

	var m map[string]any
	json.Unmarshal(data, &m)

	v, ok := m["comp_type_code"]
	if !ok {
		t.Fatal("missing comp_type_code")
	}
	// JSON numbers are float64 in Go
	if _, ok := v.(float64); !ok {
		t.Errorf("comp_type_code should be numeric, got %T", v)
	}
	if v.(float64) != 2 {
		t.Errorf("comp_type_code: got %v, want 2", v)
	}
}

// TestProgressCodeIsString verifies progress_code is always a string.
func TestProgressCodeIsString(t *testing.T) {
	rec := CorporateAction{ProgressCode: "3", DataJSON: json.RawMessage("{}")}
	data, _ := json.Marshal(rec)

	var m map[string]any
	json.Unmarshal(data, &m)

	v, ok := m["progress_code"]
	if !ok {
		t.Fatal("missing progress_code")
	}
	if _, ok := v.(string); !ok {
		t.Errorf("progress_code should be string, got %T", v)
	}
}
