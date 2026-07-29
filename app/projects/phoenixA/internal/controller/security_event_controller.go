package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/service"
)

type SecurityEventController struct {
	*core.BaseComponent
	Svc *service.SecurityEventService `infra:"dep:svc_security_event"`
}

func NewSecurityEventController() *SecurityEventController {
	return &SecurityEventController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_SECURITY_EVENT)}
}
func (c *SecurityEventController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }
func (c *SecurityEventController) Stop(ctx context.Context) error  { return c.BaseComponent.Stop(ctx) }

func (c *SecurityEventController) BatchUpsert(w http.ResponseWriter, r *http.Request) {
	var rows []*model.SecurityEvent
	if err := json.NewDecoder(r.Body).Decode(&rows); err != nil {
		writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid json"})
		return
	}
	source, eventType := chi.URLParam(r, "source"), chi.URLParam(r, "event_type")
	for _, row := range rows {
		if row != nil {
			row.Source = source
			row.EventType = eventType
			row.EventDate = normalizeDateYYYYMMDD(row.EventDate)
		}
	}
	if err := c.Svc.BatchUpsert(r.Context(), rows); err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "count": len(rows)})
}

func (c *SecurityEventController) Query(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	f := &model.SecurityEventFilters{
		StartDate: normalizeDateYYYYMMDD(q.Get("start_date")),
		EndDate:   normalizeDateYYYYMMDD(q.Get("end_date")),
		Title:     q.Get("title"),
	}
	if q.Has("security_id") {
		id, err := strconv.ParseUint(q.Get("security_id"), 10, 64)
		if err != nil || id == 0 {
			writeJSON(w, http.StatusBadRequest, apiError{Error: "invalid security_id"})
			return
		}
		f.SecurityID = id
	}
	if q.Has("security_ids") {
		ids, err := parseUint64ListStrict(q.Get("security_ids"))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiError{Error: err.Error()})
			return
		}
		f.SecurityIDs = ids
	}
	limit, offset := parseLimitOffset(r)
	rows, err := c.Svc.Query(
		r.Context(), chi.URLParam(r, "source"), chi.URLParam(r, "event_type"),
		f, limit, offset,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows})
}

func (c *SecurityEventController) LastDatesBySecurityIDs(
	w http.ResponseWriter,
	r *http.Request,
) {
	ids, err := parseUint64ListStrict(r.URL.Query().Get("security_ids"))
	if err != nil || len(ids) == 0 {
		writeJSON(
			w,
			http.StatusBadRequest,
			apiError{Error: "security_ids is required"},
		)
		return
	}
	rows, err := c.Svc.LastDatesBySecurityIDs(
		r.Context(),
		chi.URLParam(r, "source"),
		chi.URLParam(r, "event_type"),
		ids,
	)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, apiResponse[any]{Data: rows})
}
