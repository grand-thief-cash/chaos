// core/component.go
package core

import (
	"context"
	"fmt"
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
type BaseComponent struct {
	name   string
	active bool
	deps   []string
}

// NewBaseComponent 创建基础组件
func NewBaseComponent(name string, deps ...string) *BaseComponent {
	return &BaseComponent{
		name:   name,
		active: false,
		deps:   deps,
	}
}

func (c *BaseComponent) Name() string {
	return c.name
}

func (c *BaseComponent) Dependencies() []string {
	return c.deps
}

func (c *BaseComponent) IsActive() bool {
	return c.active
}

func (c *BaseComponent) SetActive(active bool) {
	c.active = active
}

func (c *BaseComponent) Start(ctx context.Context) error {
	c.active = true
	return nil
}

func (c *BaseComponent) Stop(ctx context.Context) error {
	c.active = false
	return nil
}

func (c *BaseComponent) HealthCheck() error {
	if !c.active {
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
	c.deps = append(c.deps, deps...)
}
