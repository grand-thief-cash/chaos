package controller

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type CategoryStockMapController struct {
	*core.BaseComponent
	Svc *service.CategoryStockMapService `infra:"dep:svc_category_stock_map"`
}

func NewCategoryStockMapController() *CategoryStockMapController {
	return &CategoryStockMapController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_CATEGORY_STOCK_MAP),
	}
}

func (c *CategoryStockMapController) Create(w http.ResponseWriter, r *http.Request) {
	var m model.CategoryStockMap
	if err := json.NewDecoder(r.Body).Decode(&m); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := c.Svc.Create(r.Context(), &m); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(m)
}

func (c *CategoryStockMapController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	var list []*model.CategoryStockMap
	if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := c.Svc.BatchUpsert(r.Context(), list); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func (c *CategoryStockMapController) ReplaceCategoriesForStocks(w http.ResponseWriter, r *http.Request) {
	// Expect map[stock_code] -> []category_codes
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := c.Svc.ReplaceCategoriesForStocks(r.Context(), payload); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func (c *CategoryStockMapController) ReplaceStocksForCategories(w http.ResponseWriter, r *http.Request) {
	// Expect map[category_code] -> []stock_codes
	var payload map[string][]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := c.Svc.ReplaceStocksForCategories(r.Context(), payload); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func (c *CategoryStockMapController) Delete(w http.ResponseWriter, r *http.Request) {
	categoryCode := chi.URLParam(r, "categoryCode")
	stockCode := chi.URLParam(r, "stockCode")
	if err := c.Svc.Delete(r.Context(), categoryCode, stockCode); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (c *CategoryStockMapController) ListByCategory(w http.ResponseWriter, r *http.Request) {
	categoryCode := chi.URLParam(r, "categoryCode")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	list, count, err := c.Svc.ListByCategory(r.Context(), categoryCode, page, pageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	resp := map[string]interface{}{
		"list":  list,
		"total": count,
	}
	json.NewEncoder(w).Encode(resp)
}

func (c *CategoryStockMapController) ListByStock(w http.ResponseWriter, r *http.Request) {
	stockCode := chi.URLParam(r, "stockCode")
	list, err := c.Svc.ListByStock(r.Context(), stockCode)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(list)
}
