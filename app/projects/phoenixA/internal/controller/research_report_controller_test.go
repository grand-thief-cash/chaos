package controller

import "testing"

// TestValidReportTypesAcceptsArtemisFeeds guards the rename/add drift that
// once broke morning_report downloads: artemis sends report_type values from
// EastmoneyResearchReport.SUPPORTED_REPORT_TYPES, and phoenixA must accept
// every one of them or the upsert returns 400 and the artemis task fails with
// a generic "failed to upsert N reports to phoenixA". `broker_report` was
// renamed to `morning_report`; the old name must be rejected so a stale artemis
// build is caught at the API rather than silently persisted.
//
// Keep this list in sync with:
//   - artemis: EastmoneyResearchReport.SUPPORTED_REPORT_TYPES
//   - migration: 0010_research_report_types.sql CHECK constraint
func TestValidReportTypesAcceptsArtemisFeeds(t *testing.T) {
	accepted := []string{"stock", "industry", "macro", "new_stock", "strategy", "morning_report", "other"}
	for _, rt := range accepted {
		if !validReportTypes[rt] {
			t.Errorf("validReportTypes missing %q - artemis upserts of this type are rejected with HTTP 400 (the morning_report rename once did this)", rt)
		}
	}
	// the pre-rename name must NOT be accepted; if it is, the allowlist wasn't
	// updated alongside artemis and the migration.
	if validReportTypes["broker_report"] {
		t.Errorf("validReportTypes still accepts the old %q - should be %q now", "broker_report", "morning_report")
	}
}
