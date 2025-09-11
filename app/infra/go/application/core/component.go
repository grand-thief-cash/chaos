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
