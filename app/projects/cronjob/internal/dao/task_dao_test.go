package dao

import (
	"testing"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/model"
)

// TestBuildTaskUpdateMapIncludesAllUpdatableFields guards the silent-drop
// regression: every field the controller can mutate on a task MUST be present
// in the UPDATE map, or else editing that field in the UI has no effect (the
// value is set on the in-memory struct but never written to the DB).
//
// This was triggered by `name`: updateTask set t.Name from the request, but
// the map omitted the `name` column, so renaming a task silently did nothing.
// Add a row to `want` whenever a new updatable field is introduced.
func TestBuildTaskUpdateMapIncludesAllUpdatableFields(t *testing.T) {
	tm := &model.Task{
		Name:               "renamed-task",
		Description:        "desc",
		CronExpr:           "0 0 * * * *",
		Timezone:           "Asia/Shanghai",
		ExecType:           bizConsts.ExecTypeAsync,
		HTTPMethod:         "POST",
		TargetService:      "artemis",
		TargetPath:         "/tasks/run/X",
		HeadersJSON:        `{"a":1}`,
		BodyTemplate:       `{"type":"industry"}`,
		RetryPolicyJSON:    `{"max_attempts":3}`,
		MaxConcurrency:     5,
		ConcurrencyPolicy:  bizConsts.ConcurrencySkip,
		CallbackMethod:     "POST",
		CallbackTimeoutSec: 600,
		OverlapAction:      bizConsts.OverlapActionSkip,
		FailureAction:      bizConsts.FailureActionRunNew,
		Version:            7,
	}
	got := buildTaskUpdateMap(tm)

	want := map[string]interface{}{
		"name":                 "renamed-task",
		"description":          "desc",
		"cron_expr":            "0 0 * * * *",
		"timezone":             "Asia/Shanghai",
		"exec_type":            bizConsts.ExecTypeAsync,
		"http_method":          "POST",
		"target_service":       "artemis",
		"target_path":          "/tasks/run/X",
		"headers_json":         `{"a":1}`,
		"body_template":        `{"type":"industry"}`,
		"retry_policy_json":    `{"max_attempts":3}`,
		"max_concurrency":      5,
		"concurrency_policy":   bizConsts.ConcurrencySkip,
		"callback_method":      "POST",
		"callback_timeout_sec": 600,
		"overlap_action":       bizConsts.OverlapActionSkip,
		"failure_action":       bizConsts.FailureActionRunNew,
	}
	for col, wantVal := range want {
		gotVal, ok := got[col]
		if !ok {
			t.Errorf("update map missing column %q - edits to this field are silently dropped (the `name` bug was this exact class)", col)
			continue
		}
		if gotVal != wantVal {
			t.Errorf("update map column %q = %v (%T), want %v (%T)", col, gotVal, gotVal, wantVal, wantVal)
		}
	}
	// version is bumped via a SQL expression, not a literal; just assert it's
	// present so a future refactor doesn't drop the optimistic-lock bump.
	if _, ok := got["version"]; !ok {
		t.Errorf("update map missing column \"version\" (optimistic-lock bump dropped)")
	}
}

// TestResolveTaskOrder guards the ORDER BY allowlist: the column must come from
// taskSortColumns (never raw input - SQL injection via sort_by would otherwise
// land directly in ORDER BY), the direction is a fixed ASC/DESC literal, and
// unknown/empty values fall back to the id ASC default.
func TestResolveTaskOrder(t *testing.T) {
	cases := []struct {
		name string
		f    *model.TaskListFilters
		want string
	}{
		{"nil filter defaults to id asc", nil, "id ASC"},
		{"empty defaults to id asc", &model.TaskListFilters{}, "id ASC"},
		{"id asc", &model.TaskListFilters{SortBy: "id", SortOrder: "asc"}, "id ASC"},
		{"id desc", &model.TaskListFilters{SortBy: "id", SortOrder: "desc"}, "id DESC"},
		{"name asc", &model.TaskListFilters{SortBy: "name", SortOrder: "asc"}, "name ASC"},
		{"created_at desc", &model.TaskListFilters{SortBy: "created_at", SortOrder: "desc"}, "created_at DESC"},
		{"updated_at asc", &model.TaskListFilters{SortBy: "updated_at", SortOrder: "asc"}, "updated_at ASC"},
		{"direction is case-insensitive", &model.TaskListFilters{SortBy: "id", SortOrder: "DESC"}, "id DESC"},
		{"unknown direction ignored -> asc", &model.TaskListFilters{SortBy: "id", SortOrder: "sideways"}, "id ASC"},
		{"unknown column falls back to id (dir preserved)", &model.TaskListFilters{SortBy: "random_col", SortOrder: "desc"}, "id DESC"},
		{"injection attempt in sort_by is neutralized", &model.TaskListFilters{SortBy: "id; DROP TABLE tasks; --", SortOrder: ""}, "id ASC"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := resolveTaskOrder(c.f); got != c.want {
				t.Errorf("resolveTaskOrder(%+v) = %q, want %q", c.f, got, c.want)
			}
		})
	}
}

// TestBuildTaskUpdateMapDefaultsEmptyJSON ensures empty headers/retry JSON are
// normalized to "{}" rather than persisted as an empty string (mirrors Create).
func TestBuildTaskUpdateMapDefaultsEmptyJSON(t *testing.T) {
	tm := &model.Task{HeadersJSON: "  ", RetryPolicyJSON: ""}
	got := buildTaskUpdateMap(tm)
	if got["headers_json"] != bizConsts.DEFAULT_JSON_STR {
		t.Errorf("headers_json = %v, want %q", got["headers_json"], bizConsts.DEFAULT_JSON_STR)
	}
	if got["retry_policy_json"] != bizConsts.DEFAULT_JSON_STR {
		t.Errorf("retry_policy_json = %v, want %q", got["retry_policy_json"], bizConsts.DEFAULT_JSON_STR)
	}
}
