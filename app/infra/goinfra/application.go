package goinfra

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// ApplicationManager 应用管理器
type ApplicationManager struct {
	name            string
	container       *Container
	logger          *log.Logger
	startupHooks    []func(ctx context.Context) error
	shutdownHooks   []func(ctx context.Context) error
	errorHandlers   []func(error)
	mu              sync.RWMutex
	running         bool
	shutdownCtx     context.Context
	shutdownCancel  context.CancelFunc
	wg              sync.WaitGroup
	gracefulTimeout time.Duration
}

// NewApplicationManager 创建应用管理器
func NewApplicationManager(name string) *ApplicationManager {
	ctx, cancel := context.WithCancel(context.Background())

	return &ApplicationManager{
		name:            name,
		container:       NewContainer(),
		logger:          log.New(os.Stdout, fmt.Sprintf("[%s] ", name), log.LstdFlags),
		startupHooks:    make([]func(ctx context.Context) error, 0),
		shutdownHooks:   make([]func(ctx context.Context) error, 0),
		errorHandlers:   make([]func(error), 0),
		shutdownCtx:     ctx,
		shutdownCancel:  cancel,
		gracefulTimeout: 30 * time.Second,
	}
}

// Initialize 初始化应用管理器
func (am *ApplicationManager) Initialize(ctx context.Context) error {
	am.logger.Printf("Initializing application manager '%s'", am.name)

	// 初始化容器
	if err := am.container.Initialize(ctx); err != nil {
		return fmt.Errorf("failed to initialize container: %w", err)
	}

	am.logger.Printf("Application manager '%s' initialized", am.name)
	return nil
}

// Start 启动应用
func (am *ApplicationManager) Start(ctx context.Context) error {
	am.mu.Lock()
	defer am.mu.Unlock()

	if am.running {
		return nil
	}

	am.logger.Printf("Starting application '%s'...", am.name)

	// 启动容器
	if err := am.container.Start(ctx); err != nil {
		return fmt.Errorf("failed to start container: %w", err)
	}

	// 执行启动钩子
	for _, hook := range am.startupHooks {
		if err := hook(ctx); err != nil {
			am.logger.Printf("Startup hook failed: %v", err)
			return err
		}
	}

	am.running = true
	am.logger.Printf("Application '%s' started successfully", am.name)

	// 启动信号监听
	am.wg.Add(1)
	go am.handleSignals()

	return nil
}

// Stop 停止应用
func (am *ApplicationManager) Stop(ctx context.Context) error {
	am.mu.Lock()
	defer am.mu.Unlock()

	if !am.running {
		return nil
	}

	am.logger.Printf("Stopping application '%s'...", am.name)

	// 执行关闭钩子
	for _, hook := range am.shutdownHooks {
		if err := hook(ctx); err != nil {
			am.logger.Printf("Shutdown hook failed: %v", err)
		}
	}

	// 停止容器
	if err := am.container.Stop(ctx); err != nil {
		am.logger.Printf("Warning: failed to stop container: %v", err)
	}

	am.running = false
	am.logger.Printf("Application '%s' stopped", am.name)

	return nil
}

// OnStart 启动回调
func (am *ApplicationManager) OnStart(ctx context.Context) error {
	am.logger.Printf("Application '%s' started", am.name)
	return nil
}

// OnStop 停止回调
func (am *ApplicationManager) OnStop(ctx context.Context) error {
	am.logger.Printf("Application '%s' stopped", am.name)
	return nil
}

// OnShutdown 关闭回调
func (am *ApplicationManager) OnShutdown(ctx context.Context) error {
	am.logger.Printf("Initiating shutdown for application '%s'...", am.name)

	// 创建带超时的上下文
	ctx, cancel := context.WithTimeout(ctx, am.gracefulTimeout)
	defer cancel()

	// 执行优雅关闭
	done := make(chan error, 1)
	go func() {
		done <- am.gracefulShutdown(ctx)
	}()

	select {
	case err := <-done:
		if err != nil {
			am.logger.Printf("Graceful shutdown completed with error: %v", err)
		} else {
			am.logger.Printf("Graceful shutdown completed")
		}
	case <-ctx.Done():
		am.logger.Printf("Graceful shutdown timed out, forcing shutdown")
		am.forceShutdown()
	}

	return nil
}

// Run 运行应用
func (am *ApplicationManager) Run() error {
	if err := am.Start(context.Background()); err != nil {
		return err
	}

	am.wg.Wait()
	return nil
}

// handleSignals 处理系统信号
func (am *ApplicationManager) handleSignals() {
	defer am.wg.Done()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)

	select {
	case sig := <-sigChan:
		am.logger.Printf("Received signal: %v", sig)
		am.shutdown()
	case <-am.shutdownCtx.Done():
		am.logger.Printf("Shutdown context cancelled")
	}
}

// shutdown 执行关闭
func (am *ApplicationManager) shutdown() {
	am.shutdownCancel()

	ctx := context.Background()
	if err := am.OnShutdown(ctx); err != nil {
		am.logger.Printf("Shutdown callback failed: %v", err)
	}
}

// gracefulShutdown 优雅关闭
func (am *ApplicationManager) gracefulShutdown(ctx context.Context) error {
	am.logger.Printf("Starting graceful shutdown...")

	// 按照启动顺序的逆序关闭组件
	components := am.container.ListComponents()

	for _, componentName := range components {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			component, err := am.container.Get(componentName)
			if err != nil {
				am.logger.Printf("Failed to get component '%s': %v", componentName, err)
				continue
			}

			am.logger.Printf("Stopping component: %s", componentName)
			if err := component.Stop(ctx); err != nil {
				am.logger.Printf("Failed to stop component '%s': %v", componentName, err)
			}
		}
	}

	am.logger.Printf("Graceful shutdown completed")
	return nil
}

// forceShutdown 强制关闭
func (am *ApplicationManager) forceShutdown() {
	am.logger.Printf("Forcing shutdown...")

	// 这里可以添加强制关闭的逻辑
	// 例如：取消所有goroutine，关闭文件描述符等

	am.logger.Printf("Force shutdown completed")
}

// handleError 处理错误
func (am *ApplicationManager) handleError(err error) {
	am.logger.Printf("Application error: %v", err)

	for _, handler := range am.errorHandlers {
		func() {
			defer func() {
				if r := recover(); r != nil {
					am.logger.Printf("Panic in error handler: %v", r)
				}
			}()
			handler(err)
		}()
	}
}

// AddStartupHook 添加启动钩子
func (am *ApplicationManager) AddStartupHook(hook func(ctx context.Context) error) {
	am.mu.Lock()
	defer am.mu.Unlock()
	am.startupHooks = append(am.startupHooks, hook)
}

// AddShutdownHook 添加关闭钩子
func (am *ApplicationManager) AddShutdownHook(hook func(ctx context.Context) error) {
	am.mu.Lock()
	defer am.mu.Unlock()
	am.shutdownHooks = append(am.shutdownHooks, hook)
}

// AddErrorHandler 添加错误处理器
func (am *ApplicationManager) AddErrorHandler(handler func(error)) {
	am.mu.Lock()
	defer am.mu.Unlock()
	am.errorHandlers = append(am.errorHandlers, handler)
}

// SetGracefulTimeout 设置优雅关闭超时时间
func (am *ApplicationManager) SetGracefulTimeout(timeout time.Duration) {
	am.mu.Lock()
	defer am.mu.Unlock()
	am.gracefulTimeout = timeout
}

// GetComponent 获取组件
func (am *ApplicationManager) GetComponent(name string) (Component, error) {
	return am.container.Get(name)
}

// RegisterComponent 注册组件
func (am *ApplicationManager) RegisterComponent(component Component, name string) error {
	return am.container.Register(component, name)
}

// ListComponents 列出所有组件
func (am *ApplicationManager) ListComponents() []string {
	return am.container.ListComponents()
}

// HealthCheck 健康检查
func (am *ApplicationManager) HealthCheck(ctx context.Context) map[string]interface{} {
	health := map[string]interface{}{
		"application": am.name,
		"running":     am.running,
		"components":  make(map[string]interface{}),
	}

	components := am.container.ListComponents()
	for _, componentName := range components {
		componentHealth := map[string]interface{}{
			"name":    componentName,
			"healthy": true,
		}

		component, err := am.container.Get(componentName)
		if err != nil {
			componentHealth["healthy"] = false
			componentHealth["error"] = err.Error()
		} else {
			// 如果组件实现了健康检查接口，调用它
			if healthChecker, ok := component.(HealthChecker); ok {
				if err := healthChecker.HealthCheck(ctx); err != nil {
					componentHealth["healthy"] = false
					componentHealth["error"] = err.Error()
				}
			}
		}

		health["components"].(map[string]interface{})[componentName] = componentHealth
	}

	return health
}

// ShutdownContext 获取关闭上下文
func (am *ApplicationManager) ShutdownContext() context.Context {
	return am.shutdownCtx
}

// Shutdown 触发关闭
func (am *ApplicationManager) Shutdown() {
	am.shutdown()
}

// Wait 等待关闭完成
func (am *ApplicationManager) Wait() {
	am.wg.Wait()
}
