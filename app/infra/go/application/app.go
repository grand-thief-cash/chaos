package application

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/prometheus"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/redis"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/telemetry"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
)

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
		lifecycleManager: core.NewLifecycleManager(container),
	}
}

func (app *App) boot() error {
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
	return app.bootErr
}

func (app *App) registerComponents() error {
	cfg := app.configManager.GetConfig()
	if cfg == nil {
		return fmt.Errorf("config not loaded")
	}

	if cfg.Logging != nil && cfg.Logging.Enabled {
		logFactory := logging.NewFactory()
		logComp, err := logFactory.Create(cfg.Logging)
		if err != nil {
			return fmt.Errorf("create logging component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_LOGGING, logComp); err != nil {
			return fmt.Errorf("register logging component failed: %w", err)
		}
	}

	if cfg.Telemetry != nil && cfg.Telemetry.Enabled {
		telComp := telemetry.NewTelemetryComponent(cfg.Telemetry)
		_ = app.container.Register(consts.COMPONENT_TELEMETRY, telComp)
	}

	if cfg.MySQL != nil && cfg.MySQL.Enabled {
		mysqlFactory := mysql.NewFactory()
		mysqlComp, err := mysqlFactory.Create(cfg.MySQL)
		if err != nil {
			return fmt.Errorf("create mysql component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_MYSQL, mysqlComp); err != nil {
			return fmt.Errorf("register mysql component failed: %w", err)
		}
	}

	if cfg.MySQLGORM != nil && cfg.MySQLGORM.Enabled {
		gormFactory := mysqlgorm.NewFactory()
		gormComp, err := gormFactory.Create(cfg.MySQLGORM)
		if err != nil {
			return fmt.Errorf("create mysql_gorm component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_MYSQL_GORM, gormComp); err != nil {
			return fmt.Errorf("register mysql_gorm component failed: %w", err)
		}
	}

	if cfg.Redis != nil && cfg.Redis.Enabled {
		redisFactory := redis.NewFactory()
		redisComp, err := redisFactory.Create(cfg.Redis)
		if err != nil {
			return fmt.Errorf("create redis component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_REDIS, redisComp); err != nil {
			return fmt.Errorf("register redis component failed: %w", err)
		}
	}

	if cfg.HTTPServer != nil && cfg.HTTPServer.Enabled {
		httpFactory := http_server.NewFactory(app.container)
		httpServer, err := httpFactory.Create(cfg.HTTPServer)
		if err != nil {
			return fmt.Errorf("create http_server component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_HTTP_SERVER, httpServer); err != nil {
			return fmt.Errorf("register http_server component failed: %w", err)
		}
	}

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

	if cfg.GRPCServer != nil && cfg.GRPCServer.Enabled {
		grpcSrvFactory := grpc_server.NewFactory(app.container)
		grpcSrvComp, err := grpcSrvFactory.Create(cfg.GRPCServer)
		if err != nil {
			return fmt.Errorf("create grpc_server component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_GRPC_SERVER, grpcSrvComp); err != nil {
			return fmt.Errorf("register grpc_server component failed: %w", err)
		}
	}

	if cfg.Prometheus != nil && cfg.Prometheus.Enabled {
		promFactory := prometheus.NewFactory()
		promComp, err := promFactory.Create(cfg.Prometheus)
		if err != nil {
			return fmt.Errorf("create prometheus component failed: %w", err)
		}
		if err = app.container.Register(consts.COMPONENT_PROMETHEUS, promComp); err != nil {
			return fmt.Errorf("register prometheus component failed: %w", err)
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

// Run sets up an OS signal context and blocks until SIGINT/SIGTERM.
func (app *App) Run() error {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGINT, syscall.SIGTERM, syscall.SIGTERM)
	defer stop()
	return app.RunWithContext(ctx)
}

// RunWithContext starts components and blocks until context done,
// then performs graceful shutdown.
func (app *App) RunWithContext(ctx context.Context) error {
	if err := app.boot(); err != nil {
		return err
	}

	if err := app.lifecycleManager.StartAll(ctx); err != nil {
		return err
	}

	// Block until context canceled.
	<-ctx.Done()

	// Graceful shutdown.
	app.lifecycleManager.StopAll(context.Background())
	return nil
}

func (app *App) Shutdown(ctx context.Context) {
	app.lifecycleManager.StopAll(ctx)
}
