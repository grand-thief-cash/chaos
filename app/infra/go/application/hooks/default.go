// hooks/default.go
package hooks

import (
	"context"
	"log"
)

func init() {
	// 注册默认的启动前钩子
	if err := RegisterHook("log_startup", BeforeStart, func(ctx context.Context) error {
		log.Println("Application is starting...")
		return nil
	}, 100); err != nil {
		log.Printf("Failed to register default hook: %v", err)
	}

	// 注册默认的启动后钩子
	if err := RegisterHook("log_started", AfterStart, func(ctx context.Context) error {
		log.Println("Application started successfully")
		return nil
	}, 100); err != nil {
		log.Printf("Failed to register default hook: %v", err)
	}

	// 注册默认的关闭前钩子
	if err := RegisterHook("log_shutdown", BeforeShutdown, func(ctx context.Context) error {
		log.Println("Application is shutting down...")
		return nil
	}, 100); err != nil {
		log.Printf("Failed to register default hook: %v", err)
	}

	// 注册默认的关闭后钩子
	if err := RegisterHook("log_shutdown_complete", AfterShutdown, func(ctx context.Context) error {
		log.Println("Application shutdown completed")
		return nil
	}, 100); err != nil {
		log.Printf("Failed to register default hook: %v", err)
	}
}

// 全局钩子管理器
var globalHookManager = NewManager()

// RegisterHook 向全局钩子管理器注册钩子
func RegisterHook(name string, phase Phase, function HookFunc, priority int) error {
	hook := &Hook{
		Name:     name,
		Phase:    phase,
		Function: function,
		Priority: priority,
	}
	return globalHookManager.Register(hook)
}

// ExecuteHooks 执行全局钩子管理器中指定阶段的钩子
func ExecuteHooks(ctx context.Context, phase Phase) error {
	return globalHookManager.Execute(ctx, phase)
}

// GetGlobalHookManager 获取全局钩子管理器
func GetGlobalHookManager() *Manager {
	return globalHookManager
}
