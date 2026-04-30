// core/component.go
package core

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
)

// Component 定义组件的基本接口
type Component interface {
	Name() string
	Start(ctx context.Context) error
	Stop(ctx context.Context) error
	HealthCheck() error
	Dependencies() []string
	IsActive() bool
}

// BaseComponent 提供组件的基础实现
// active 使用 atomic.Bool 保证并发安全（HealthCheck / IsActive 可能在 Start/Stop 的同时被调用）。
// deps 使用 sync.RWMutex 保护，因为 AddDependencies 可能与 Dependencies 并发调用。
type BaseComponent struct {
	name   string
	active atomic.Bool
	depsMu sync.RWMutex
	deps   []string
}

// NewBaseComponent 创建基础组件
func NewBaseComponent(name string, deps ...string) *BaseComponent {
	return &BaseComponent{
		name: name,
		deps: deps,
	}
}

func (c *BaseComponent) Name() string {
	return c.name
}

func (c *BaseComponent) Dependencies() []string {
	c.depsMu.RLock()
	defer c.depsMu.RUnlock()
	out := make([]string, len(c.deps))
	copy(out, c.deps)
	return out
}

func (c *BaseComponent) IsActive() bool {
	return c.active.Load()
}

func (c *BaseComponent) SetActive(active bool) {
	c.active.Store(active)
}

func (c *BaseComponent) Start(ctx context.Context) error {
	c.active.Store(true)
	return nil
}

func (c *BaseComponent) Stop(ctx context.Context) error {
	c.active.Store(false)
	return nil
}

func (c *BaseComponent) HealthCheck() error {
	if !c.active.Load() {
		return fmt.Errorf("component %s is not active", c.name)
	}
	return nil
}

// AddDependencies 允许在组件尚未启动前动态扩展其依赖（用于框架外部按需追加启动顺序约束）
// 注意：应在生命周期 StartAll 调用之前（通常在各自 init()/注册阶段）使用。
func (c *BaseComponent) AddDependencies(deps ...string) {
	if len(deps) == 0 {
		return
	}
	c.depsMu.Lock()
	defer c.depsMu.Unlock()
	c.deps = append(c.deps, deps...)
}
