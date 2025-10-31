package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/service"
)

type RunMgmtController struct {
	*core.BaseComponent
	RunSvc   *service.RunService         `infra:"dep:run_service"`
	Exec     *service.Executor           `infra:"dep:executor"`
	Progress *service.RunProgressManager `infra:"dep:run_progress_mgr"`
	Cleanup  *service.RunCleanupService  `infra:"dep:run_cleanup"`
}

func NewRunMgmtController() *RunMgmtController {
	return &RunMgmtController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_RUN_MGMT)}
}

func parseRunFilters(r *http.Request) (statuses []bizConsts.RunStatus, from, to *time.Time, limit, offset int) {
	q := r.URL.Query()
	limit = 50
	if v := q.Get("limit"); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i > 0 && i <= 500 {
			limit = i
		}
	}
	if v := q.Get("offset"); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i >= 0 {
			offset = i
		}
	}
	if v := q.Get("status"); v != "" {
		parts := strings.Split(v, ",")
		for _, p := range parts {
			p = strings.TrimSpace(strings.ToUpper(p))
			if p == "" {
				continue
			}
			statuses = append(statuses, bizConsts.RunStatus(p))
		}
	}
	parseTime := func(key string) *time.Time {
		if s := strings.TrimSpace(q.Get(key)); s != "" {
			if t, err := time.Parse(time.RFC3339, s); err == nil {
				return &t
			}
		}
		return nil
	}
	from = parseTime("from")
	to = parseTime("to")
	return
}

// listRunsByTask lists recent runs for a task (migrated from task controller)
func (c *RunMgmtController) listRunsByTask(w http.ResponseWriter, r *http.Request, taskID int64) {
	statuses, from, to, limit, offset := parseRunFilters(r)
	list, err := c.RunSvc.ListByTaskFiltered(r.Context(), taskID, statuses, from, to, limit, offset)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"items": list, "limit": limit, "offset": offset})
}

func (c *RunMgmtController) listActiveRuns(w http.ResponseWriter, r *http.Request) {
	statuses, from, to, limit, offset := parseRunFilters(r)
	list, err := c.RunSvc.ListActiveFiltered(r.Context(), statuses, from, to, limit, offset)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"items": list, "limit": limit, "offset": offset})
}

func (c *RunMgmtController) getRun(w http.ResponseWriter, r *http.Request, runID int64) {
	run, err := c.RunSvc.Get(r.Context(), runID)
	if err != nil {
		writeErr(w, 404, err.Error())
		return
	}
	writeJSON(w, run)
}

func (c *RunMgmtController) cancelRun(w http.ResponseWriter, r *http.Request, runID int64) {
	c.Exec.CancelRun(runID)
	if c.Progress != nil {
		c.Progress.Clear(runID)
	}
	writeJSON(w, map[string]any{"canceled": true})
}

func (c *RunMgmtController) getRunProgress(w http.ResponseWriter, r *http.Request, runID int64) {
	if c.Progress == nil {
		writeJSON(w, map[string]any{"run_id": runID, "percent": 0, "message": "progress_not_enabled"})
		return
	}
	p := c.Progress.Get(runID)
	if p == nil {
		writeJSON(w, map[string]any{"run_id": runID, "percent": 0, "message": "no_progress"})
		return
	}
	writeJSON(w, p)
}

func (c *RunMgmtController) setRunProgress(w http.ResponseWriter, r *http.Request, runID int64) {
	if c.Progress == nil {
		writeErr(w, 400, "progress_not_enabled")
		return
	}
	var req struct {
		Current int64  `json:"current"`
		Total   int64  `json:"total"`
		Message string `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, err.Error())
		return
	}
	if req.Total < 0 || req.Current < 0 {
		writeErr(w, 400, "negative_values_not_allowed")
		return
	}
	if req.Total == 0 && req.Current > 0 {
		writeErr(w, 400, "current_requires_total")
		return
	}
	run, err := c.RunSvc.Get(r.Context(), runID)
	if err != nil {
		writeErr(w, 404, "run_not_found")
		return
	}
	switch run.Status {
	case bizConsts.Scheduled, bizConsts.Running, bizConsts.CallbackPending:
	default:
		writeErr(w, 400, "run_not_active")
		return
	}
	c.Progress.Set(runID, req.Current, req.Total, req.Message)
	writeJSON(w, map[string]any{"updated": true})
}

func (c *RunMgmtController) finalizeCallback(w http.ResponseWriter, r *http.Request, runID int64) {
	var req struct {
		Result string `json:"result"`
		Code   int    `json:"code"`
		Body   string `json:"body"`
		Error  string `json:"error_message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, err.Error())
		return
	}
	run, err := c.RunSvc.Get(r.Context(), runID)
	if err != nil {
		writeErr(w, 404, "run_not_found")
		return
	}
	if run.Status != bizConsts.CallbackPending {
		writeErr(w, 400, "run_not_in_callback_pending")
		return
	}
	switch strings.ToLower(strings.TrimSpace(req.Result)) {
	case "success":
		if req.Code == 0 {
			req.Code = 200
		}
		if err := c.RunSvc.MarkCallbackSuccess(r.Context(), runID, req.Code, req.Body); err != nil {
			writeErr(w, 500, err.Error())
			return
		}
	case "failed_timeout":
		if err := c.RunSvc.MarkFailedTimeout(r.Context(), runID, defaultOr(req.Error, "callback_deadline_exceeded")); err != nil {
			writeErr(w, 500, err.Error())
			return
		}
	case "failed":
		if err := c.RunSvc.MarkCallbackFailed(r.Context(), runID, defaultOr(req.Error, "callback_failed")); err != nil {
			writeErr(w, 500, err.Error())
			return
		}
	default:
		writeErr(w, 400, "invalid_result")
		return
	}
	if c.Progress != nil {
		c.Progress.Clear(runID)
	}
	writeJSON(w, map[string]any{"updated": true})
}

func (c *RunMgmtController) summaryRuns(w http.ResponseWriter, r *http.Request) {
	counts, err := c.Cleanup.Summary(r.Context(), 100000)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	// gather terminal stats per task
	result := make(map[string]any)
	terminal := []bizConsts.RunStatus{bizConsts.Success, bizConsts.Failed, bizConsts.FailedTimeout, bizConsts.Canceled}
	// simple aggregate: total runs and terminal percentages per task
	aggregates := make(map[int64]map[string]any)
	for taskID, total := range counts {
		aggregates[taskID] = map[string]any{"total_runs": total}
	}
	// naive: re-query recent runs per task limited to e.g. 1000 to estimate terminal portion
	for taskID := range counts {
		list, _ := c.RunSvc.ListByTaskFiltered(r.Context(), taskID, nil, nil, nil, 1000, 0)
		var termCnt int
		for _, run := range list {
			for _, ts := range terminal {
				if run.Status == ts {
					termCnt++
					break
				}
			}
		}
		if len(list) > 0 {
			aggregates[taskID]["terminal_ratio_estimate"] = float64(termCnt) / float64(len(list))
		} else {
			aggregates[taskID]["terminal_ratio_estimate"] = 0.0
		}
	}
	result["counts"] = counts
	result["aggregates"] = aggregates
	writeJSON(w, result)
}

func (c *RunMgmtController) cleanupRuns(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Mode          string  `json:"mode"`
		TaskID        int64   `json:"task_id"`
		MaxAgeSeconds int64   `json:"max_age_seconds"`
		Keep          int     `json:"keep"`
		IDs           []int64 `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, err.Error())
		return
	}
	mode := strings.ToLower(strings.TrimSpace(req.Mode))
	var deleted int64
	var err error
	switch mode {
	case "age":
		if req.MaxAgeSeconds <= 0 {
			writeErr(w, 400, "invalid_max_age_seconds")
			return
		}
		deleted, err = c.Cleanup.CleanupByAge(r.Context(), req.TaskID, time.Duration(req.MaxAgeSeconds)*time.Second)
	case "count":
		deleted, err = c.Cleanup.CleanupByKeep(r.Context(), req.TaskID, req.Keep)
	case "ids":
		deleted, err = c.Cleanup.CleanupByIDs(r.Context(), req.IDs)
	default:
		writeErr(w, 400, "invalid_mode")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, map[string]any{"deleted": deleted})
}
