// core/lifecycle.go
package core

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
)

// LifecycleManager 生命周期管理器
// Removed internal OS signal handling to centralize at App level; lifecycle now purely orchestrates component start/stop & hooks.
type LifecycleManager struct {
	container      *Container
	hookManager    *hooks.Manager
	mutex          sync.RWMutex
	shutdownCalled bool
	timeout        time.Duration
}

// NewLifecycleManager 创建新的生命周期管理器（使用新的空 hook manager）
func NewLifecycleManager(container *Container) *LifecycleManager {
	return &LifecycleManager{
		container:   container,
		hookManager: hooks.NewManager(),
		timeout:     30 * time.Second,
	}
}

// NewLifecycleManagerWithManager 允许注入已有的 hook manager（用于复用全局默认 hooks）
func NewLifecycleManagerWithManager(container *Container, hm *hooks.Manager) *LifecycleManager {
	if hm == nil {
		hm = hooks.NewManager()
	}
	return &LifecycleManager{
		container:   container,
		hookManager: hm,
		timeout:     30 * time.Second,
	}
}

// SetTimeout 设置组件启动/停止超时时间
func (lm *LifecycleManager) SetTimeout(timeout time.Duration) {
	lm.timeout = timeout
}

// AddHook 添加生命周期钩子
func (lm *LifecycleManager) AddHook(name string, phase hooks.Phase, function hooks.HookFunc, priority int) error {
	hook := &hooks.Hook{
		Name:     name,
		Phase:    phase,
		Function: function,
		Priority: priority,
	}
	return lm.hookManager.Register(hook)
}

// StartAll 启动所有组件
func (lm *LifecycleManager) StartAll(ctx context.Context) error {
	if err := lm.hookManager.Execute(ctx, hooks.BeforeStart); err != nil {
		return fmt.Errorf("before_start hooks failed: %w", err)
	}

	// 新增：先验证依赖完整性（含环、缺失）
	components, err := lm.container.ValidateDependencies()
	if err != nil {
		return fmt.Errorf("dependency validation failed: %w", err)
	}

	for _, comp := range components {
		startCtx, cancel := context.WithTimeout(ctx, lm.timeout)
		err := comp.Start(startCtx)
		cancel()

		if err != nil {
			log.Printf("Failed to start component %s: %v", comp.Name(), err)
			// Attempt to cleanup the failed component itself if it became active partially.
			if comp.IsActive() {
				_ = comp.Stop(context.Background())
			}
			// Stop previously started components.
			lm.stopStartedComponents(context.Background(), components, comp.Name())
			return fmt.Errorf("failed to start component %s: %w", comp.Name(), err)
		}

		log.Printf("Component %s started successfully", comp.Name())
	}

	if err := lm.hookManager.Execute(ctx, hooks.AfterStart); err != nil {
		log.Printf("after_start hooks failed: %v", err)
	}

	return nil
}

// StopAll 停止所有组件
func (lm *LifecycleManager) StopAll(ctx context.Context) {
	lm.mutex.Lock()
	if lm.shutdownCalled {
		lm.mutex.Unlock()
		return
	}
	lm.shutdownCalled = true
	lm.mutex.Unlock()

	log.Println("Initiating shutdown sequence...")

	if err := lm.hookManager.Execute(ctx, hooks.BeforeShutdown); err != nil {
		log.Printf("before_shutdown hooks failed: %v", err)
	}

	components, err := lm.container.SortComponentsByDependencies()
	if err != nil {
		log.Printf("Failed to sort components for shutdown: %v", err)
		registered := lm.container.ListRegistered()
		components = make([]Component, 0, len(registered))
		for _, comp := range registered {
			components = append(components, comp)
		}
	}

	for i := len(components) - 1; i >= 0; i-- {
		comp := components[i]
		if !comp.IsActive() {
			continue
		}

		log.Printf("Stopping component: %s", comp.Name())
		stopCtx, cancel := context.WithTimeout(ctx, lm.timeout)
		if err := comp.Stop(stopCtx); err != nil {
			log.Printf("Error stopping component %s: %v", comp.Name(), err)
		}
		cancel()
	}

	if err := lm.hookManager.Execute(ctx, hooks.AfterShutdown); err != nil {
		log.Printf("after_shutdown hooks failed: %v", err)
	}

	log.Println("Shutdown sequence completed")
}

func (lm *LifecycleManager) stopStartedComponents(ctx context.Context, components []Component, failedComponentName string) {
	for i := len(components) - 1; i >= 0; i-- {
		comp := components[i]
		if comp.Name() == failedComponentName {
			continue // skip failed component (already attempted cleanup above)
		}
		if comp.IsActive() {
			stopCtx, cancel := context.WithTimeout(ctx, lm.timeout)
			if err := comp.Stop(stopCtx); err != nil {
				log.Printf("Error stopping component %s during cleanup: %v", comp.Name(), err)
			}
			cancel()
		}
	}
}
