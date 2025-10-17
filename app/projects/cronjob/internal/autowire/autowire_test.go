package autowire_test

import (
	"context"
	"testing"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/autowire"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	cronConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/registry_ext" // ensure builders registered via init
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/scheduler"
)

func loadConfig(t *testing.T) *config.AppConfig {
	cm := config.NewConfigManager("development", "./config/config.yaml")
	if err := cm.LoadConfig(); err != nil {
		// Fail the test early if config cannot be loaded.
		// Some tests may not require full config; if needed we could supply a minimal stub.
		// For now we assert correctness of the existing example config.
		t.Fatalf("load config failed: %v", err)
	}
	return cm.GetConfig()
}

func TestAutowireExecutorAndScheduler(t *testing.T) {
	cfg := loadConfig(t)
	c := core.NewContainer()

	if err := registry.BuildAndRegisterAll(cfg, c); err != nil {
		t.Fatalf("registry build failed: %v", err)
	}
	if err := autowire.InjectAll(c); err != nil {
		t.Fatalf("autowire failed: %v", err)
	}

	execComp, err := c.Resolve(cronConsts.COMP_SVC_EXECUTOR)
	if err != nil {
		t.Fatalf("resolve executor failed: %v", err)
	}
	exec, ok := execComp.(*executor.Executor)
	if !ok {
		t.Fatalf("executor type assertion failed")
	}
	if exec.TaskDao == nil || exec.RunDao == nil {
		t.Fatalf("executor dependencies not injected: taskDao=%v runDao=%v", exec.TaskDao, exec.RunDao)
	}

	engineComp, err := c.Resolve(cronConsts.COMP_SVC_SCHEDULER)
	if err != nil {
		t.Fatalf("resolve scheduler failed: %v", err)
	}
	engine, ok := engineComp.(*scheduler.Engine)
	if !ok {
		t.Fatalf("scheduler type assertion failed")
	}
	if engine.TaskDao == nil || engine.RunDao == nil || engine.Exec == nil {
		t.Fatalf("scheduler dependencies not injected: taskDao=%v runDao=%v exec=%v", engine.TaskDao, engine.RunDao, engine.Exec)
	}

	// Optional: start minimal lifecycle to ensure start ordering uses injected deps.
	lm := core.NewLifecycleManager(c)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := lm.StartAll(ctx); err != nil {
		// Accept failure only if unrelated to autowire; but treat any error as test failure for simplicity.
		t.Fatalf("lifecycle start failed: %v", err)
	}
	lm.StopAll(context.Background())
}
