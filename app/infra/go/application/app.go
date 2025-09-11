// app.go
package infra_go

import (
	"context"
	"fmt"
	"log"

	"go.uber.org/zap"

	"github.com/grand-thief-cash/chaos/app/infra/infra_go/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/infra_go/config"
	"github.com/grand-thief-cash/chaos/app/infra/infra_go/core"
	"github.com/grand-thief-cash/chaos/app/infra/infra_go/hooks"
)

// App 应用程序实例
type App struct {
	container        *core.Container
	lifecycleManager *core.LifecycleManager
	config           *config.AppConfig
	configLoader     *config.Loader
	configValidator  *config.Validator
	logger           logging.Logger
}

// NewApp 创建新的应用实例
func NewApp() *App {
	container := core.NewContainer()
	lifecycleManager := core.NewLifecycleManager(container)

	return &App{
		container:        container,
		lifecycleManager: lifecycleManager,
		configLoader:     config.NewLoader("GOINFRA_"),
		configValidator:  config.NewValidator(),
	}
}

// LoadConfig 加载配置文件
func (app *App) LoadConfig(configPath string) error {
	cfg, err := app.configLoader.LoadConfig(configPath)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	if err := app.configValidator.Validate(cfg); err != nil {
		return fmt.Errorf("config validation failed: %w", err)
	}

	app.config = cfg
	log.Printf("Configuration loaded successfully from %s", configPath)

	// 如果配置中启用了日志组件，自动注册
	if err := app.autoRegisterLoggingComponent(); err != nil {
		return fmt.Errorf("failed to register logging component: %w", err)
	}

	return nil
}

// autoRegisterLoggingComponent 自动注册日志组件
func (app *App) autoRegisterLoggingComponent() error {
	if app.config != nil && app.config.Logging.Enabled {
		factory := logging.NewFactory()
		component, err := factory.Create(&app.config.Logging)
		if err != nil {
			return fmt.Errorf("failed to create logging component: %w", err)
		}

		if err := app.container.Register("logger", component); err != nil {
			return fmt.Errorf("failed to register logging component: %w", err)
		}

		log.Println("Logger component auto-registered")
	}
	return nil
}

// GetLogger 获取日志记录器
func (app *App) GetLogger() (logging.Logger, error) {
	if app.logger != nil {
		return app.logger, nil
	}

	component, err := app.container.Resolve("logger")
	if err != nil {
		return nil, fmt.Errorf("logger component not found: %w", err)
	}

	loggerComponent, ok := component.(*logging.ZapLoggerComponent)
	if !ok {
		return nil, fmt.Errorf("invalid logger component type")
	}

	app.logger = loggerComponent.GetLogger()
	return app.logger, nil
}

// GetZapLogger 获取原始的zap.Logger
func (app *App) GetZapLogger() (*zap.Logger, error) {
	component, err := app.container.Resolve("logger")
	if err != nil {
		return nil, fmt.Errorf("logger component not found: %w", err)
	}

	loggerComponent, ok := component.(*logging.ZapLoggerComponent)
	if !ok {
		return nil, fmt.Errorf("invalid logger component type")
	}

	return loggerComponent.GetZapLogger(), nil
}

// RegisterComponent 注册组件
func (app *App) RegisterComponent(name string, component core.Component) error {
	return app.container.Register(name, component)
}

// AddHook 添加生命周期钩子
func (app *App) AddHook(name string, phase hooks.Phase, function hooks.HookFunc, priority int) error {
	return app.lifecycleManager.AddHook(name, phase, function, priority)
}

// GetComponent 获取组件
func (app *App) GetComponent(name string) (core.Component, error) {
	return app.container.Resolve(name)
}

// GetConfig 获取配置
func (app *App) GetConfig() *config.AppConfig {
	return app.config
}

// Run 启动应用
func (app *App) Run() error {
	return app.RunWithContext(context.Background())
}

// RunWithContext 使用指定上下文启动应用
func (app *App) RunWithContext(ctx context.Context) error {
	if err := app.lifecycleManager.StartAll(ctx); err != nil {
		return err
	}

	app.lifecycleManager.WaitForShutdown(ctx)
	return nil
}

// Shutdown 手动关闭应用
func (app *App) Shutdown(ctx context.Context) {
	app.lifecycleManager.StopAll(ctx)
}
