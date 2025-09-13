// app.go
package application

import (
	"context"
	"fmt"
	"path/filepath"
	"sync"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
)

// App 应用程序实例
type App struct {
	container        *core.Container
	lifecycleManager *core.LifecycleManager
	configManager    *config.ConfigManager

	bootOnce sync.Once
	bootErr  error
	booted   bool
}

func NewApp(env string, configPath string) *App {

	abs := configPath
	if p, err := filepath.Abs(configPath); err == nil {
		abs = p
	}

	container := core.NewContainer()
	return &App{
		configManager:    config.NewConfigManager(env, abs),
		container:        container,
		lifecycleManager: core.NewLifecycleManager(container), // will overwrite container below
	}
}

func (app *App) registerComponents() error {
	cfg := app.configManager.GetConfig()
	if cfg == nil {
		return fmt.Errorf("config not loaded")
	}

	// logging
	if cfg.Logging != nil && cfg.Logging.Enabled {
		logFactory := logging.NewFactory()
		logComp, err := logFactory.Create(cfg.Logging)
		if err != nil {
			return fmt.Errorf("create logging component failed: %w", err)
		}
		if err = app.container.Register("logger", logComp); err != nil {
			return fmt.Errorf("register logging component failed: %w", err)
		}
	}

	// grpc clients (inject logger if present)
	if cfg.GRPCClients != nil && cfg.GRPCClients.Enabled {
		grpcFactory := grpc_client.NewFactory()
		grpcComp, err := grpcFactory.Create(cfg.GRPCClients)
		if err != nil {
			return fmt.Errorf("create grpc clients component failed: %w", err)
		}
		if err = app.container.Register("grpc_clients", grpcComp); err != nil {
			return fmt.Errorf("register grpc clients component failed: %w", err)
		}
	}

	return nil
}

func (app *App) GetComponent(name string) (core.Component, error) {
	return app.container.Resolve(name)
}

func (app *App) GetConfig() *config.AppConfig {
	if app.configManager == nil {
		return nil
	}
	return app.configManager.GetConfig()
}

func (app *App) AddHook(name string, phase hooks.Phase, fn hooks.HookFunc, priority int) error {
	return app.lifecycleManager.AddHook(name, phase, fn, priority)
}

func (app *App) Run() error {
	app.bootOnce.Do(func() {
		if err := app.configManager.LoadConfig(); err != nil {
			app.bootErr = fmt.Errorf("load config failed: %w", err)
			return
		}
		if err := app.registerComponents(); err != nil {
			app.bootErr = fmt.Errorf("register components failed: %w", err)
			return
		}
		app.booted = true
	})
	if app.bootErr != nil {
		return app.bootErr
	}

	return app.RunWithContext(context.Background())
}

func (app *App) RunWithContext(ctx context.Context) error {
	if err := app.lifecycleManager.StartAll(ctx); err != nil {
		return err
	}
	app.lifecycleManager.WaitForShutdown(ctx)
	return nil
}

func (app *App) Shutdown(ctx context.Context) {
	app.lifecycleManager.StopAll(ctx)
}
