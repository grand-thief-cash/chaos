// core/container.go
package core

import (
	"fmt"
	"sort"
	"strings"
	"sync"
)

// Container 依赖注入容器
type Container struct {
	components map[string]Component
	configs    map[string]interface{}
	mutex      sync.RWMutex
}

// NewContainer 创建新的容器实例
func NewContainer() *Container {
	return &Container{
		components: make(map[string]Component),
		configs:    make(map[string]interface{}),
	}
}

// Register 注册组件到容器
func (c *Container) Register(name string, component Component) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	if _, exists := c.components[name]; exists {
		return fmt.Errorf("component %s already registered", name)
	}

	c.components[name] = component
	return nil
}

// Resolve 从容器中获取组件
func (c *Container) Resolve(name string) (Component, error) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	component, exists := c.components[name]
	if !exists {
		return nil, fmt.Errorf("component %s not found", name)
	}

	return component, nil
}

// ListRegistered 列出所有已注册的组件
func (c *Container) ListRegistered() map[string]Component {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	result := make(map[string]Component)
	for name, comp := range c.components {
		result[name] = comp
	}
	return result
}

// SetConfig 设置组件配置
func (c *Container) SetConfig(name string, config interface{}) {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	c.configs[name] = config
}

// GetConfig 获取组件配置
func (c *Container) GetConfig(name string) (interface{}, bool) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	config, exists := c.configs[name]
	return config, exists
}

// SortComponentsByDependencies 根据依赖关系对组件进行拓扑排序
func (c *Container) SortComponentsByDependencies() ([]Component, error) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	visited := make(map[string]bool)
	visiting := make(map[string]bool)
	result := make([]Component, 0, len(c.components))

	var visit func(string) error
	visit = func(name string) error {
		if visiting[name] {
			return fmt.Errorf("circular dependency detected involving component %s", name)
		}
		if visited[name] {
			return nil
		}

		component, exists := c.components[name]
		if !exists {
			return fmt.Errorf("component %s not found", name)
		}

		visiting[name] = true

		for _, dep := range component.Dependencies() {
			if err := visit(dep); err != nil {
				return err
			}
		}

		visiting[name] = false
		visited[name] = true
		result = append(result, component)

		return nil
	}

	names := make([]string, 0, len(c.components))
	for name := range c.components {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		if err := visit(name); err != nil {
			return nil, err
		}
	}

	return result, nil
}

// Replace 替换已注册但未激活的组件（主要用于测试）
func (c *Container) Replace(name string, component Component) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	existing, exists := c.components[name]
	if !exists {
		return fmt.Errorf("component %s not registered", name)
	}
	if existing.IsActive() {
		return fmt.Errorf("component %s is active; cannot replace", name)
	}
	c.components[name] = component
	return nil
}

// ValidateDependencies 检查所有组件声明的依赖是否都已注册；返回拓扑排序结果（不启动）
func (c *Container) ValidateDependencies() ([]Component, error) {
	c.mutex.RLock()
	missing := make(map[string][]string)
	for name, comp := range c.components {
		for _, dep := range comp.Dependencies() {
			if _, ok := c.components[dep]; !ok {
				missing[name] = append(missing[name], dep)
			}
		}
	}
	c.mutex.RUnlock()
	if len(missing) > 0 {
		var parts []string
		for k, v := range missing {
			parts = append(parts, fmt.Sprintf("%s -> [%s]", k, strings.Join(v, ",")))
		}
		return nil, fmt.Errorf("missing component dependencies: %s", strings.Join(parts, "; "))
	}
	// 借用现有拓扑排序做环检测
	ordered, err := c.SortComponentsByDependencies()
	if err != nil {
		return nil, err
	}
	return ordered, nil
}
