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
	//fmt.Printf("Request Headers: %+v\n", r.Header)
	ip := r.Header.Get("X-Caller-Ip")
	port := r.Header.Get("X-Caller-Port")
	addr := fmt.Sprintf("http://%s%s", ip, port)
	progressEndpoint := r.Header.Get("X-Callback-Progress")
	resEndpoint := r.Header.Get("X-Callback-Res")
	progressEndpoint = fmt.Sprintf(progressEndpoint, runID)
	progressCallbackURL := fmt.Sprintf("%s%s", addr, progressEndpoint)
	resEndpoint = fmt.Sprintf(resEndpoint, runID)
	resCallbackURL := fmt.Sprintf("%s%s", addr, resEndpoint)

	go func() {
		steps := 20
		ctx := context.Background()

		client := &http.Client{}
		reportProgress := func(current int, msg string) error {
			payload := map[string]any{"current": current, "total": steps, "message": msg}
			b, _ := json.Marshal(payload)

			logging.Debug(ctx, fmt.Sprintf("Prepared progress report: %s", progressCallbackURL))
			req, err := http.NewRequestWithContext(ctx, http.MethodPost, progressCallbackURL, bytes.NewReader(b))
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
			err := reportProgress(i, fmt.Sprintf("step %d/%d", i, steps))
			if err != nil {
				logging.Error(ctx, fmt.Sprintf("Error reporting progress: %+v", err))
			}
			time.Sleep(time.Duration(rand.Intn(2)) * time.Second)
		}
		go func() {
			err := reportCallback(resCallbackURL, "success", 200, "all steps done", "")
			if err != nil {
				logging.Error(ctx, fmt.Sprintf("Error reporting callback: %+v", err))
			}
		}()
	}()

	resp := map[string]interface{}{"run_id": runID, "result": "Created"}
	writeJSON(w, resp)
}

func reportCallback(apiURL string, result string, code int, body, errorMessage string) error {
	payload := map[string]any{
		"result":        result,       // "success", "failed", "failed_timeout"
		"code":          code,         // HTTP code, e.g. 200
		"body":          body,         // response body or output
		"error_message": errorMessage, // error details if any
	}
	data, _ := json.Marshal(payload)
	req, err := http.NewRequest("POST", apiURL, bytes.NewBuffer(data))
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
