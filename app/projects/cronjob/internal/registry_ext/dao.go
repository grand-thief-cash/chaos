package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
)

func init() {
	registry.RegisterAuto(bizConsts.COMP_DAO_TASK, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewTaskDao("cronjob"), nil
	})
	registry.RegisterAuto(bizConsts.COMP_DAO_RUN, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, dao.NewRunDao("cronjob"), nil
	})
}
