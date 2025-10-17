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

	// executor component (builder deps retained for ordering, but construction no longer resolves manually)
	registry.RegisterWithDeps(consts.COMP_SVC_EXECUTOR, []string{consts.COMP_DAO_TASK, consts.COMP_DAO_RUN}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, executor.NewExecutor(cronjobCfg.Executor), nil
	})

	// scheduler engine depends (build ordering) on executor and daos; autowire will inject.
	registry.RegisterWithDeps(consts.COMP_SVC_SCHEDULER, []string{consts.COMP_DAO_TASK, consts.COMP_DAO_RUN, consts.COMP_SVC_EXECUTOR}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		return true, scheduler.NewEngine(cronjobCfg.Scheduler), nil
	})
}
