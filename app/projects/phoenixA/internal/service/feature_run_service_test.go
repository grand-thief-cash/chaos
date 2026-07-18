package service

import (
	"strings"
	"testing"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func validRunRequestForTest() model.FeatureRunCreateRequest {
	return model.FeatureRunCreateRequest{
		ProducerService: "artemis", TriggerType: "api",
		AsOfTime:       time.Date(2026, 7, 14, 15, 0, 0, 0, time.FixedZone("CST", 8*60*60)),
		DataCutoffTime: time.Date(2026, 7, 14, 14, 0, 0, 0, time.FixedZone("CST", 8*60*60)),
		SourceProfile:  "home", Market: "zh_a", UniverseHash: strings.Repeat("a", 64),
		CodeRevision: "git-sha", RootFeatureVersionIDs: []uint64{9, 3},
		DependencyPlanChecksum: strings.Repeat("b", 64),
		Parameters:             map[string]any{"window": 20, "winsorize": true},
	}
}

func TestNormalizeRunRequestProducesCanonicalFingerprint(t *testing.T) {
	first := validRunRequestForTest()
	second := validRunRequestForTest()
	second.RootFeatureVersionIDs = []uint64{3, 9}
	second.Parameters = map[string]any{"winsorize": true, "window": 20}

	if err := normalizeRunRequest(&first); err != nil {
		t.Fatalf("normalize first request: %v", err)
	}
	if err := normalizeRunRequest(&second); err != nil {
		t.Fatalf("normalize second request: %v", err)
	}
	if first.RequestFingerprint != second.RequestFingerprint {
		t.Fatalf("canonical fingerprints differ: %s != %s", first.RequestFingerprint, second.RequestFingerprint)
	}
	if first.RootFeatureVersionIDs[0] != 3 || !validUUID(first.RunID) {
		t.Fatalf("request was not normalized: %#v", first)
	}

	changedPlan := validRunRequestForTest()
	changedPlan.DependencyPlanChecksum = strings.Repeat("c", 64)
	if err := normalizeRunRequest(&changedPlan); err != nil {
		t.Fatalf("normalize changed plan: %v", err)
	}
	if changedPlan.RequestFingerprint == first.RequestFingerprint {
		t.Fatal("dependency plan checksum must participate in the request fingerprint")
	}
}

func TestNormalizeRunRequestValidatesFingerprints(t *testing.T) {
	req := validRunRequestForTest()
	req.DependencyPlanChecksum = "not-a-checksum"
	assertFeatureErrorCode(t, normalizeRunRequest(&req), "DEPENDENCY_PLAN_CHECKSUM_INVALID")

	req = validRunRequestForTest()
	req.RequestFingerprint = strings.Repeat("d", 64)
	assertFeatureErrorCode(t, normalizeRunRequest(&req), "REQUEST_FINGERPRINT_MISMATCH")

	req = validRunRequestForTest()
	req.DataCutoffTime = req.AsOfTime.Add(time.Second)
	assertFeatureErrorCode(t, normalizeRunRequest(&req), "DATA_CUTOFF_VIOLATION")
}

func TestFeatureRunStateMachineAndHeartbeat(t *testing.T) {
	if !validRunStateUpdate(model.FeatureStateUpdateRequest{ExpectedStatus: "queued", NewStatus: "planning"}) {
		t.Fatal("queued -> planning should be valid")
	}
	if validRunStateUpdate(model.FeatureStateUpdateRequest{ExpectedStatus: "succeeded", NewStatus: "running"}) {
		t.Fatal("terminal runs must not reopen")
	}
	now := time.Now().UTC()
	if !validRunStateUpdate(model.FeatureStateUpdateRequest{ExpectedStatus: "running", NewStatus: "running", HeartbeatAt: &now}) {
		t.Fatal("active-state heartbeat should be valid")
	}
	if validRunStateUpdate(model.FeatureStateUpdateRequest{ExpectedStatus: "running", NewStatus: "running"}) {
		t.Fatal("same-state update without heartbeat should be invalid")
	}
	if validRunStateUpdate(model.FeatureStateUpdateRequest{ExpectedStatus: "succeeded", NewStatus: "succeeded", HeartbeatAt: &now}) {
		t.Fatal("terminal-state heartbeat should be invalid")
	}
}

func TestNormalizeItemQualitySummary(t *testing.T) {
	summary := normalizeItemQualitySummary(model.FeatureRunItemUpdateRequest{
		NewStatus: "succeeded", InputCount: 10, OutputCount: 10,
		ValidCount: 8, MissingCount: 1, InvalidCount: 1,
		QualitySummary: map[string]any{"plugin": "constant_one"},
	})
	if summary["status"] != "succeeded" || summary["gate_passed"] != true {
		t.Fatalf("terminal quality status missing: %#v", summary)
	}
	if summary["coverage_ratio"] != 0.8 || summary["output_ratio"] != 1.0 {
		t.Fatalf("quality ratios are incorrect: %#v", summary)
	}
	if summary["plugin"] != "constant_one" {
		t.Fatalf("plugin quality details were lost: %#v", summary)
	}
}

func TestReconcileStaleRunsValidatesCutoffBeforeUsingDao(t *testing.T) {
	service := &FeatureRunService{}
	_, err := service.ReconcileStaleRuns(t.Context(), model.FeatureStaleRunReconcileRequest{
		ProducerService: "artemis", StaleBefore: time.Now().UTC().Add(time.Minute),
	})
	assertFeatureErrorCode(t, err, "STALE_BEFORE_INVALID")
	_, err = service.ReconcileStaleRuns(t.Context(), model.FeatureStaleRunReconcileRequest{
		StaleBefore: time.Now().UTC().Add(-time.Minute),
	})
	assertFeatureErrorCode(t, err, "PRODUCER_SERVICE_REQUIRED")
}

func TestExpandBackfillTimesMonthlyClampsToMonthEnd(t *testing.T) {
	start := time.Date(2024, 1, 31, 9, 30, 0, 0, time.UTC)
	got, err := expandBackfillTimes(model.FeatureBackfillCreateRequest{
		StartAsOf: start, EndAsOf: time.Date(2024, 4, 30, 9, 30, 0, 0, time.UTC), Step: "monthly",
	})
	if err != nil {
		t.Fatalf("expand monthly backfill: %v", err)
	}
	wantDays := []int{31, 29, 31, 30}
	if len(got) != len(wantDays) {
		t.Fatalf("expanded dates = %v", got)
	}
	for i, day := range wantDays {
		if got[i].Day() != day {
			t.Errorf("date %d = %s, want day %d", i, got[i], day)
		}
	}
}

func TestExpandBackfillTimesRejectsDuplicateExplicitDates(t *testing.T) {
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err := expandBackfillTimes(model.FeatureBackfillCreateRequest{
		StartAsOf: start, EndAsOf: start.AddDate(0, 0, 1), Step: "explicit",
		ExplicitAsOfTimes: []time.Time{start, start},
	})
	assertFeatureErrorCode(t, err, "BACKFILL_TIMES_INVALID")
}

func TestCreateBackfillRejectsUnimplementedTradingCalendar(t *testing.T) {
	service := &FeatureRunService{}
	_, _, err := service.CreateBackfill(t.Context(), model.FeatureBackfillCreateRequest{CalendarCode: "SSE"})
	assertFeatureErrorCode(t, err, "BACKFILL_CALENDAR_UNSUPPORTED")
}

func TestBackfillCutoffPolicies(t *testing.T) {
	asOf := time.Date(2026, 7, 14, 8, 0, 0, 0, time.UTC)
	got, err := backfillCutoff(map[string]any{"mode": "lag_seconds", "seconds": 3600}, asOf)
	if err != nil || !got.Equal(asOf.Add(-time.Hour)) {
		t.Fatalf("integer lag cutoff = %s, %v", got, err)
	}
	key := asOf.Format(time.RFC3339Nano)
	want := asOf.Add(-2 * time.Hour)
	got, err = backfillCutoff(map[string]any{"mode": "explicit", "values": map[string]any{key: want.Format(time.RFC3339Nano)}}, asOf)
	if err != nil || !got.Equal(want) {
		t.Fatalf("explicit cutoff = %s, %v", got, err)
	}
	_, err = backfillCutoff(map[string]any{"mode": "lag_seconds", "seconds": -1}, asOf)
	assertFeatureErrorCode(t, err, "BACKFILL_CUTOFF_POLICY_INVALID")
}

func TestEqualUint64Slices(t *testing.T) {
	if !equalUint64Slices([]uint64{1, 2}, []uint64{1, 2}) || equalUint64Slices([]uint64{1, 2}, []uint64{2, 1}) {
		t.Fatal("equalUint64Slices must compare stable ordered sets")
	}
}

func TestValidateFeatureRunID(t *testing.T) {
	assertFeatureErrorCode(t, validateFeatureRunID("not-a-uuid"), "RUN_ID_INVALID")
	if err := validateFeatureRunID("5cecd0dc-5c46-4ef7-a71a-caa53b0fe8a9"); err != nil {
		t.Fatalf("valid UUID rejected: %v", err)
	}
}
