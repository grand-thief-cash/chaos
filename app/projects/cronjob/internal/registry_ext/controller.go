package registry_ext

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	appconsts "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/api"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/scheduler"
)

func init() {
	// Ensure http_server starts after our controller component by extending its runtime dep graph.
	registry.ExtendRuntimeDependencies(appconsts.COMPONENT_HTTP_SERVER, consts.COMP_CTRL_TASK_MGMT)

	// executor component
	registry.RegisterWithDeps(consts.COMP_CTRL_TASK_MGMT, []string{
		consts.COMP_DAO_TASK, consts.COMP_DAO_RUN, consts.COMP_SVC_EXECUTOR, consts.COMP_SVC_SCHEDULER,
	}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		compTask, err := c.Resolve(consts.COMP_DAO_TASK)
		if err != nil {
			return true, nil, fmt.Errorf("resolve task_dao failed: %w", err)
		}
		taskDao, ok := compTask.(dao.TaskDao)
		if !ok {
			return true, nil, fmt.Errorf("task_dao type assertion failed")
		}

		compRun, err := c.Resolve(consts.COMP_DAO_RUN)
		if err != nil {
			return true, nil, fmt.Errorf("resolve run_dao failed: %w", err)
		}
		runDao, ok := compRun.(dao.RunDao)
		if !ok {
			return true, nil, fmt.Errorf("run_dao type assertion failed")
		}

		compExecutor, err := c.Resolve(consts.COMP_SVC_EXECUTOR)
		if err != nil {
			return true, nil, fmt.Errorf("resolve executor failed: %w", err)
		}
		execComp, ok := compExecutor.(*executor.Executor)
		if !ok {
			return true, nil, fmt.Errorf("executor type assertion failed")
		}

		compScheduler, err := c.Resolve(consts.COMP_SVC_SCHEDULER)
		if err != nil {
			return true, nil, fmt.Errorf("resolve scheduler_engine failed: %w", err)
		}
		schedComp, ok := compScheduler.(*scheduler.Engine)
		if !ok {
			return true, nil, fmt.Errorf("scheduler_engine type assertion failed")
		}

		return true, api.NewTaskMgmtController(taskDao, runDao, execComp, schedComp), nil
	})
}
