package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	bizConfig "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/scheduler"
)

func init() {
	cronjobCfg := bizConfig.GetBizConfig()

	registry.RegisterAuto(consts.COMP_SVC_EXECUTOR, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, executor.NewExecutor(cronjobCfg.Executor), nil
	})
	registry.RegisterAuto(consts.COMP_SVC_SCHEDULER, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, scheduler.NewEngine(cronjobCfg.Scheduler), nil
	})
}
