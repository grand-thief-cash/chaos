package api

import (
	"context"
	"encoding/json"
	"net/http"
	"sort"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

type MetaController struct {
	*core.BaseComponent
}

func NewMetaController() *MetaController {
	return &MetaController{BaseComponent: core.NewBaseComponent(bizConsts.COMP_CTRL_META_MGMT)}
}

func (c *MetaController) ListClients(w http.ResponseWriter, r *http.Request) {
	// 这里应该从全局配置获取 http_clients
	// 例如 application.GetApp().Config().HTTPClientsConfig.Clients
	// 这里假设有 application.GetApp().Config().HTTPClientsConfig.Clients
	clientsCfg := application.GetApp().GetConfig().HTTPClient.Clients

	names := make([]string, 0, len(clientsCfg))
	for k := range clientsCfg {
		if k == "default" {
			continue
		}
		names = append(names, k)
	}
	sort.Strings(names)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "success",
		"data":   names,
	})
}

// Start implements core.Component
func (c *MetaController) Start(ctx context.Context) error { return c.BaseComponent.Start(ctx) }

// Stop implements core.Component
func (c *MetaController) Stop(ctx context.Context) error { return c.BaseComponent.Stop(ctx) }
