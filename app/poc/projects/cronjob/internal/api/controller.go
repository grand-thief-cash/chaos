package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"strconv"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type POCController struct {
	*core.BaseComponent
}

func NewPOCController() *POCController {
	return &POCController{BaseComponent: core.NewBaseComponent("poc_ctrl", consts.COMPONENT_LOGGING)}
}

func (tmc *POCController) giveAnswer(w http.ResponseWriter, r *http.Request) {
	res := make(map[string]interface{})
	randNum := rand.Int31n(13)
	logging.Info(r.Context(), fmt.Sprintf("sleeping for %d seconds", randNum))
	time.Sleep(time.Duration(randNum) * time.Second)
	res["result"] = time.Now().Unix()
	writeJSON(w, res)
}

// giveAnswerAndProgress runs a synthetic long job and reports progress to cronjob service via HTTP.
// Query params:
//
//	run_id    optional externally provided run id; if absent uses current unix ms + jitter
//	steps     number of steps (default 20, max 2000)
//	delay_ms  delay per step (default 300ms, max 5000ms)
//	cron_addr override cronjob base address (default http://localhost:9999)
//	verbose   if set to 1 returns per-step status array
func (tmc *POCController) giveAnswerAndProgress(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	var runID int64
	if v := q.Get("run_id"); v != "" {
		if parsed, err := strconv.ParseInt(v, 10, 64); err == nil && parsed > 0 {
			runID = parsed
		}
	}
	if runID == 0 {
		logging.Error(r.Context(), "run_id is required")
	}
	go func() {
		steps := 20
		ctx := context.Background()
		cronAddr := q.Get("cron_addr")
		if cronAddr == "" {
			cronAddr = "http://localhost:9999"
		}

		client := &http.Client{}
		reportProgress := func(current int, msg string) error {
			payload := map[string]any{"current": current, "total": steps, "message": msg}
			b, _ := json.Marshal(payload)
			url := fmt.Sprintf("%s/api/v1/runs/%d/progress", cronAddr, runID)
			logging.Debug(ctx, fmt.Sprintf("Prepared progress report: %s", url))
			req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(b))
			if err != nil {
				return err
			}
			req.Header.Set("Content-Type", "application/json")
			resp, err := client.Do(req)
			if err != nil {
				logging.Debug(ctx, fmt.Sprintf("Error reporting progress: %s", err))
				return err
			}
			bodyBytes, err := io.ReadAll(resp.Body)

			defer resp.Body.Close()
			if resp.StatusCode >= 300 {
				logging.Info(ctx, fmt.Sprintf("Reported progress report resp: %s", string(bodyBytes)))
				return fmt.Errorf("cronjob progress endpoint returned %d", resp.StatusCode)
			}
			if err != nil {
				logging.Error(ctx, fmt.Sprintf("Error reading response body: %v", err))
			} else {
				logging.Info(ctx, fmt.Sprintf("Reported progress report resp: %s", string(bodyBytes)))
			}
			return nil
		}

		for i := 1; i <= steps; i++ {
			reportProgress(i, fmt.Sprintf("step %d/%d", i, steps))
			time.Sleep(time.Duration(rand.Intn(2)) * time.Second)
		}
		go func() {
			reportCallback(cronAddr+"/api/v1/runs", runID, "success", 200, "all steps done", "")
		}()
	}()

	resp := map[string]interface{}{"run_id": runID, "result": "Created"}
	writeJSON(w, resp)
}

func reportCallback(apiURL string, runID int64, result string, code int, body, errorMessage string) error {
	payload := map[string]any{
		"result":        result,       // "success", "failed", "failed_timeout"
		"code":          code,         // HTTP code, e.g. 200
		"body":          body,         // response body or output
		"error_message": errorMessage, // error details if any
	}
	data, _ := json.Marshal(payload)
	url := fmt.Sprintf("%s/%d/callback", apiURL, runID)
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("callback failed: %s", resp.Status)
	}
	return nil
}
