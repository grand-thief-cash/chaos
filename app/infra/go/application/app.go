package application

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"sync"
	"syscall"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
)

type App struct {
	container        *core.Container
	lifecycleManager *core.LifecycleManager
	configManager    *config.ConfigManager

	bootOnce sync.Once
	bootErr  error
	booted   bool

	shutdownTimeout time.Duration
}

func NewApp(env string, configPath string) *App {
	abs := configPath
	if p, err := filepath.Abs(configPath); err == nil {
		abs = p
	}
	container := core.NewContainer()
	// Use global hook manager so default hooks (registered in hooks/default.go) are effective.
	lm := core.NewLifecycleManagerWithManager(container, hooks.GetGlobalHookManager())
	return &App{
		configManager:    config.NewConfigManager(env, abs),
		container:        container,
		lifecycleManager: lm,
		shutdownTimeout:  30 * time.Second,
	}
}

// SetShutdownTimeout allows customizing graceful shutdown timeout.
func (app *App) SetShutdownTimeout(d time.Duration) { app.shutdownTimeout = d }

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

	// New unified registration via registry. Each component self-registers its builder in its registry/*.go init().
	if err := registry.BuildAndRegisterAll(cfg, app.container); err != nil {
		return err
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

// Run 根据平台与环境变量自动选择基础或增强（双信号 + 超时 + Windows 控制事件）模式。
// 选择策略：
//  1. 若设置 GOINFRA_DISABLE_ENHANCED=1 -> 使用基础模式
//  2. 若设置 GOINFRA_FORCE_ENHANCED=1  -> 使用增强模式
//  3. 默认：Windows 上使用增强模式，其它平台基础模式
//
// 环境变量（增强模式下可用）：
//
//	GOINFRA_DISABLE_FORCE_EXIT=1   禁用超时/第二信号强制退出
//	GOINFRA_FORCE_EXIT_CODE=<int>  自定义强制退出码（默认 1）
func (app *App) Run() error {
	if app.shouldUseEnhanced() {
		return app.runEnhanced()
	}
	return app.runBasic()
}

// runBasic == 旧 Run 行为：简单监听 SIGINT/SIGTERM。
func (app *App) runBasic() error {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return app.RunWithContext(ctx)
}

// runEnhanced == 原 RunInGoland 逻辑（双信号 + 超时 + 可控强退 + Windows 控制台事件）。
func (app *App) runEnhanced() error {
	sigCh := make(chan os.Signal, 2)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	ctx, cancel := context.WithCancel(context.Background())
	defer func() {
		signal.Stop(sigCh)
		close(sigCh)
	}()

	installPlatformControlHandler(cancel, app.shutdownTimeout)

	errCh := make(chan error, 1)
	go func() { errCh <- app.RunWithContext(ctx) }()

	forceExit := func(reason string) {
		if _, disable := os.LookupEnv("GOINFRA_DISABLE_FORCE_EXIT"); disable {
			log.Printf("[graceful] force exit suppressed (%s)", reason)
			return
		}
		exitCode := 1
		if v := os.Getenv("GOINFRA_FORCE_EXIT_CODE"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				exitCode = n
			}
		}
		log.Printf("[graceful] forcing process exit (code=%d) reason=%s", exitCode, reason)
		os.Exit(exitCode)
	}

	for {
		select {
		case sig := <-sigCh:
			if sig == nil {
				return <-errCh
			}
			log.Printf("Received signal %s, initiating graceful shutdown (timeout %s)...", sig, app.shutdownTimeout)
			// 超时强退计时器
			go func() {
				select {
				case <-time.After(app.shutdownTimeout):
					forceExit("graceful-timeout")
				}
			}()
			// 第二信号强制退出
			go func() {
				second := <-sigCh
				if second != nil {
					forceExit("second-signal")
				}
			}()
			cancel()
		case err := <-errCh:
			return err
		}
	}
}

func (app *App) shouldUseEnhanced() bool {
	if _, off := os.LookupEnv("GOINFRA_DISABLE_ENHANCED"); off {
		return false
	}
	if _, on := os.LookupEnv("GOINFRA_FORCE_ENHANCED"); on {
		return true
	}
	return runtime.GOOS == "windows" // 默认仅 Windows 使用增强模式
}

// installPlatformControlHandler 在 Windows 安装控制台事件处理，其它平台 no-op。
func installPlatformControlHandler(cancel context.CancelFunc, timeout time.Duration) {
	if runtime.GOOS != "windows" {
		return
	}
	core.InstallWindowsCtrlHandler(cancel, timeout)
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
