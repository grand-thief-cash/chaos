package dao

import (
	"reflect"
	"testing"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestDetectFeatureDependencyCycle(t *testing.T) {
	tests := []struct {
		name  string
		edges map[uint64][]uint64
		want  []uint64
	}{
		{name: "acyclic", edges: map[uint64][]uint64{1: {2, 3}, 2: {4}}},
		{name: "self cycle", edges: map[uint64][]uint64{7: {7}}, want: []uint64{7, 7}},
		{name: "multi node cycle", edges: map[uint64][]uint64{1: {2}, 2: {3}, 3: {1}}, want: []uint64{1, 2, 3, 1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := DetectFeatureDependencyCycle(tt.edges); !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("DetectFeatureDependencyCycle() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestLatestBackfillRuns(t *testing.T) {
	attempt1, attempt2 := 1, 2
	first := time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC)
	second := first.AddDate(0, 0, 1)
	runs := []model.FeatureRun{
		{RunID: "old", AsOfTime: first, BackfillAttempt: &attempt1, Status: "failed"},
		{RunID: "second", AsOfTime: second, BackfillAttempt: &attempt1, Status: "succeeded"},
		{RunID: "retry", AsOfTime: first, BackfillAttempt: &attempt2, Status: "queued"},
	}

	got := LatestBackfillRuns(runs)
	if len(got) != 2 || got[0].RunID != "retry" || got[1].RunID != "second" {
		t.Fatalf("LatestBackfillRuns() = %#v", got)
	}
}

func TestNumericValuesEqualIgnoresComputedAtAndCanonicalizesFlags(t *testing.T) {
	value := 1.25
	observed := time.Date(2026, 7, 14, 8, 0, 0, 0, time.UTC)
	left := model.FeatureNumericValue{
		ObservedAt: observed, Value: &value, ValueStatus: "valid",
		QualityFlags: model.JSONValue(`{"a":1,"b":2}`), ComputedAt: observed,
	}
	right := left
	right.QualityFlags = model.JSONValue(`{"b":2,"a":1}`)
	right.ComputedAt = observed.Add(time.Hour)
	if !numericValuesEqual(left, right) {
		t.Fatal("semantically identical numeric values should be idempotent")
	}
	right.ValueStatus = "invalid"
	if numericValuesEqual(left, right) {
		t.Fatal("different value status must conflict")
	}
}

func TestFeatureTerminalStatusHelpers(t *testing.T) {
	for _, status := range []string{"succeeded", "partially_succeeded", "failed", "cancelled", "aborted"} {
		if !IsTerminalRunStatus(status) {
			t.Errorf("run status %s should be terminal", status)
		}
	}
	if IsTerminalRunStatus("validating") {
		t.Fatal("validating run must not be terminal")
	}
	for _, status := range []string{"succeeded", "failed", "skipped"} {
		if !IsTerminalItemStatus(status) {
			t.Errorf("item status %s should be terminal", status)
		}
	}
}

func TestFeatureAvailabilityStatusAggregation(t *testing.T) {
	readyField := model.FeatureDataFieldAvailability{Status: "ready"}
	unknownField := model.FeatureDataFieldAvailability{Status: "unknown"}
	missingField := model.FeatureDataFieldAvailability{Status: "missing"}
	if got := featureDataStatus(nil, 0, 0); got != "ready" {
		t.Fatalf("no data dependencies = %s, want ready", got)
	}
	if got := featureDataStatus([]model.FeatureDataFieldAvailability{unknownField}, 0, 1); got != "unknown" {
		t.Fatalf("unknown dependency = %s", got)
	}
	if got := featureDataStatus([]model.FeatureDataFieldAvailability{readyField, unknownField}, 1, 1); got != "partial" {
		t.Fatalf("mixed observed dependency = %s", got)
	}
	if got := featureDataStatus([]model.FeatureDataFieldAvailability{missingField}, 0, 0); got != "missing" {
		t.Fatalf("missing dependency = %s", got)
	}
}

func TestFeatureExecutionReadinessRequiresExecutableContract(t *testing.T) {
	definition := model.FeatureDefinition{EntityType: "security", ValueType: "number"}
	if got := featureExecutionReadiness(definition, "valid", "published", "ready", "ready", "loadable"); got != "ready" {
		t.Fatalf("executable contract = %s", got)
	}
	if got := featureExecutionReadiness(definition, "valid", "published", "ready", "unknown", "loadable"); got != "unknown" {
		t.Fatalf("unknown source data = %s", got)
	}
	definition.EntityType = "document"
	if got := featureExecutionReadiness(definition, "valid", "published", "ready", "ready", "loadable"); got != "not_ready" {
		t.Fatalf("unsupported entity = %s", got)
	}
}
