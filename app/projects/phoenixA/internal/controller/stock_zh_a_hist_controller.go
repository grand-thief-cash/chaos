package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type StockZhAHistController struct {
	*core.BaseComponent
	Svc *service.StockZhAHistService `infra:"dep:stock_zh_a_hist_service"`
}

func NewStockZhAHistController() *StockZhAHistController {
	return &StockZhAHistController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_STOCK_ZH_A_HIST, consts.COMPONENT_LOGGING),
	}
}

func (c *StockZhAHistController) Start(ctx context.Context) error {
	return c.BaseComponent.Start(ctx) // Or c.BaseComponent.Start(ctx) if embedded pointer
}

func (c *StockZhAHistController) Stop(ctx context.Context) error {
	return c.BaseComponent.Stop(ctx)
}

// BatchSaveRequest used json.RawMessage to defer unmarshalling
type BatchSaveRequest struct {
	Frequency string          `json:"frequency"`
	Adjust    string          `json:"adjust"`
	Data      json.RawMessage `json:"data"`
}

func (c *StockZhAHistController) BatchSaveStockData(w http.ResponseWriter, r *http.Request) {
	var req BatchSaveRequest
	ctx := r.Context()
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := c.Svc.BatchSaveStockData(ctx, req.Frequency, req.Adjust, req.Data); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(ctx, "BatchSaveStockData error: %+v", err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "ok"}); err != nil {
		logging.Errorf(ctx, "failed to encode response: %v", err)
	}
}

func (c *StockZhAHistController) GetStockLastUpdate(w http.ResponseWriter, r *http.Request) {
	frequency := r.URL.Query().Get("frequency")
	adjust := r.URL.Query().Get("adjust")

	if frequency == "" || adjust == "" {
		http.Error(w, "Missing frequency or adjust", http.StatusBadRequest)
		return
	}

	var codes []string
	codeListStr := r.URL.Query().Get("code_list")
	if codeListStr != "" {
		codes = strings.Split(codeListStr, ",")
	} else {
		codes = r.URL.Query()["code"]
	}

	dates, err := c.Svc.GetStockLastUpdates(r.Context(), frequency, adjust, codes)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(dates); err != nil {
		logging.Errorf(r.Context(), "failed to encode response: %v", err)
	}
}

// GetDailyByCodeDateRange
// GET /api/v1/stock/hist/range?code=000001&start_date=2024-01-01&end_date=2024-01-31&frequency=daily&adjust=nf&limit=1000&offset=0&fields=open,close
func (c *StockZhAHistController) GetDailyByCodeDateRange(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	q := r.URL.Query()

	code := strings.TrimSpace(q.Get("code"))
	startDate := strings.TrimSpace(q.Get("start_date"))
	endDate := strings.TrimSpace(q.Get("end_date"))

	if code == "" || startDate == "" || endDate == "" {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "missing code or start_date or end_date"})
		return
	}

	frequency := strings.TrimSpace(q.Get("frequency"))
	adjust := strings.TrimSpace(q.Get("adjust"))
	limit, offset := parseLimitOffset(r)

	fields := parseFieldsParam(q.Get("fields"))
	if len(fields) > 0 {
		fields = append(fields, "date") // Ensure date is always included
	}

	list, err := c.Svc.GetStockHistSelected(ctx, frequency, adjust, code, startDate, endDate, limit, offset, fields)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
		logging.Errorf(ctx, "GetDailyByCodeDateRange error: %+v", err)
		return
	}

	for _, it := range list {
		if it != nil {
			it.Date = normalizeDateYYYYMMDD(it.Date)
		}
	}

	writeJSON(w, http.StatusOK, apiResponse[any]{Data: list})
}
