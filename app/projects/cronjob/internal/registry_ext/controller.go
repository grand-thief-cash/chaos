package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	appconsts "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/api"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

func init() {
	// Ensure http_server starts after our controller component by extending its runtime dep graph.
	registry.ExtendRuntimeDependencies(appconsts.COMPONENT_HTTP_SERVER, consts.COMP_CTRL_TASK_MGMT)

	registry.RegisterAuto(consts.COMP_CTRL_TASK_MGMT, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, api.NewTaskMgmtController(), nil
	})
}
