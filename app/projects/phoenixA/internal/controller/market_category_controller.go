package controller

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type MarketCategoryController struct {
	*core.BaseComponent
	SvcMktCategroyMairui *service.MarketCategoryMairui `infra:"dep:svc_market_category_mairui"`
	//SvcMktCategroySWHY   *service.IMarketCategoryService[model.CategorySWHY, model.CategoryFiltersSWHY]     `infra:"dep:market_category_swhy_service"`
}

func NewMarketCategoryController() *MarketCategoryController {
	return &MarketCategoryController{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_MARKET_CATEGORY),
	}
}

func (c *MarketCategoryController) Create(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")

	var err error
	if source == bizConsts.DATA_SOURCE_MAIRUI {
		var m model.CategoryMairui
		if err = json.NewDecoder(r.Body).Decode(&m); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err = c.SvcMktCategroyMairui.Create(ctx, &m); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(m)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}
}

func (c *MarketCategoryController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")
	if source == "" {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}
	if source == bizConsts.DATA_SOURCE_MAIRUI {
		var list []*model.CategoryMairui
		if err := json.NewDecoder(r.Body).Decode(&list); err != nil {
			logging.Errorf(ctx, "Failed to decode batch upsert request: %v", err)
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err := c.SvcMktCategroyMairui.BatchUpsert(ctx, list); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusOK)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}

}

func (c *MarketCategoryController) Update(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")

	code := chi.URLParam(r, "code")
	if source == bizConsts.DATA_SOURCE_MAIRUI {
		var m model.CategoryMairui
		if err := json.NewDecoder(r.Body).Decode(&m); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		m.Code = code
		if err := c.SvcMktCategroyMairui.Update(ctx, &m); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(m)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}
}

func (c *MarketCategoryController) Get(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")
	if source == bizConsts.DATA_SOURCE_MAIRUI {

		code := chi.URLParam(r, "code")
		m, err := c.SvcMktCategroyMairui.Get(ctx, code)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(m)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}
}

func (c *MarketCategoryController) Delete(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")

	code := chi.URLParam(r, "code")
	if source == bizConsts.DATA_SOURCE_MAIRUI {
		if err := c.SvcMktCategroyMairui.Delete(ctx, code); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}
}

func (c *MarketCategoryController) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	source := chi.URLParam(r, "source")

	if source == bizConsts.DATA_SOURCE_MAIRUI {
		page, _ := strconv.Atoi(r.URL.Query().Get("page"))
		pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))

		f := &model.CategoryFiltersMairui{}
		if v := r.URL.Query().Get("parent_code"); v != "" {
			f.ParentCode = &v
		}
		if v := r.URL.Query().Get("level"); v != "" {
			if i, err := strconv.ParseUint(v, 10, 8); err == nil {
				u8 := uint8(i)
				f.Level = &u8
			}
		}
		if v := r.URL.Query().Get("type1"); v != "" {
			if i, err := strconv.ParseUint(v, 10, 8); err == nil {
				u8 := uint8(i)
				f.Type1 = &u8
			}
		}
		if v := r.URL.Query().Get("type2"); v != "" {
			if i, err := strconv.ParseUint(v, 10, 16); err == nil {
				u16 := uint16(i)
				f.Type2 = &u16
			}
		}

		list, count, err := c.SvcMktCategroyMairui.List(ctx, f, page, pageSize)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		resp := map[string]interface{}{
			"list":  list,
			"total": count,
		}
		json.NewEncoder(w).Encode(resp)
	} else {
		http.Error(w, "source is required", http.StatusBadRequest)
		return
	}

}
