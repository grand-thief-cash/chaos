package registry_ext

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	bizConfig "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/scheduler"
)

func init() {
	cronjobCfg := bizConfig.GetBizConfig()

	// executor component
	registry.RegisterWithDeps("executor", []string{"task_dao", "run_dao"}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		compTask, err := c.Resolve("task_dao")
		if err != nil {
			return true, nil, fmt.Errorf("resolve task_dao failed: %w", err)
		}
		taskDao, ok := compTask.(dao.TaskDao)
		if !ok {
			return true, nil, fmt.Errorf("task_dao type assertion failed")
		}

		compRun, err := c.Resolve("run_dao")
		if err != nil {
			return true, nil, fmt.Errorf("resolve run_dao failed: %w", err)
		}
		runDao, ok := compRun.(dao.RunDao)
		if !ok {
			return true, nil, fmt.Errorf("run_dao type assertion failed")
		}

		return true, executor.NewExecutor(cronjobCfg.Executor, taskDao, runDao), nil
	})

	// scheduler engine depends on executor (runtime) and daos
	registry.RegisterWithDeps("scheduler_engine", []string{"task_dao", "run_dao", "executor"}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		compTask, err := c.Resolve("task_dao")
		if err != nil {
			return true, nil, fmt.Errorf("resolve task_dao failed: %w", err)
		}
		taskDao, ok := compTask.(dao.TaskDao)
		if !ok {
			return true, nil, fmt.Errorf("task_dao type assertion failed")
		}

		compRun, err := c.Resolve("run_dao")
		if err != nil {
			return true, nil, fmt.Errorf("resolve run_dao failed: %w", err)
		}
		runDao, ok := compRun.(dao.RunDao)
		if !ok {
			return true, nil, fmt.Errorf("run_dao type assertion failed")
		}

		compExecutor, err := c.Resolve("executor")
		if err != nil {
			return true, nil, fmt.Errorf("resolve executor failed: %w", err)
		}
		execComp, ok := compExecutor.(*executor.Executor)
		if !ok {
			return true, nil, fmt.Errorf("executor type assertion failed")
		}

		return true, scheduler.NewEngine(taskDao, runDao, execComp, cronjobCfg.Scheduler), nil
	})
}
