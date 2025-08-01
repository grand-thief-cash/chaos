package goinfra

import (
	"context"
	"fmt"
	"log"
	"reflect"
	"strings"
	"sync"
)

// Component 组件接口
type Component interface {
	Name() string
	Dependencies() []string
	Initialize(ctx context.Context, container *Container) error
	Start(ctx context.Context) error
	Stop(ctx context.Context) error
}

// Lifecycle 生命周期接口
type Lifecycle interface {
	OnStart(ctx context.Context) error
	OnStop(ctx context.Context) error
	OnShutdown(ctx context.Context) error
}

// Configurable 可配置组件接口
type Configurable interface {
	Configure(config map[string]interface{}) error
	GetConfig() map[string]interface{}
}

// ComponentState 组件状态
type ComponentState int

const (
	StateInitialized ComponentState = iota
	StateStarting
	StateRunning
	StateStopping
	StateStopped
	StateError
)

func (s ComponentState) String() string {
	return [...]string{"initialized", "starting", "running", "stopping", "stopped", "error"}[s]
}

// Container 依赖注入容器
type Container struct {
	components     map[string]Component
	componentTypes map[string]reflect.Type
	dependencies   map[string]map[string]bool
	reverseDeps    map[string]map[string]bool
	mu             sync.RWMutex
	initialized    bool
	running        bool
	shutdownCtx    context.Context
	shutdownCancel context.CancelFunc
	shutdownWg     sync.WaitGroup
}

// NewContainer 创建新的容器
func NewContainer() *Container {
	ctx, cancel := context.WithCancel(context.Background())
	return &Container{
		components:     make(map[string]Component),
		componentTypes: make(map[string]reflect.Type),
		dependencies:   make(map[string]map[string]bool),
		reverseDeps:    make(map[string]map[string]bool),
		shutdownCtx:    ctx,
		shutdownCancel: cancel,
	}
}

// Register 注册组件
func (c *Container) Register(component Component, name string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.components[name]; exists {
		return fmt.Errorf("component '%s' already exists", name)
	}

	c.components[name] = component
	c.componentTypes[name] = reflect.TypeOf(component)

	// 记录依赖关系
	c.dependencies[name] = make(map[string]bool)
	for _, dep := range component.Dependencies() {
		c.dependencies[name][dep] = true
		if c.reverseDeps[dep] == nil {
			c.reverseDeps[dep] = make(map[string]bool)
		}
		c.reverseDeps[dep][name] = true
	}

	// 检查循环依赖
	if err := c.checkCircularDependencies(); err != nil {
		return err
	}

	return nil
}

// Get 获取组件
func (c *Container) Get(name string) (Component, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	component, exists := c.components[name]
	if !exists {
		return nil, fmt.Errorf("component '%s' not found", name)
	}
	return component, nil
}

// Has 检查组件是否存在
func (c *Container) Has(name string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	_, exists := c.components[name]
	return exists
}

// Remove 移除组件
func (c *Container) Remove(name string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.components[name]; !exists {
		return fmt.Errorf("component '%s' not found", name)
	}

	// 移除依赖关系
	for dep := range c.dependencies[name] {
		delete(c.reverseDeps[dep], name)
	}

	for revDep := range c.reverseDeps[name] {
		delete(c.dependencies[revDep], name)
	}

	delete(c.components, name)
	delete(c.componentTypes, name)
	delete(c.dependencies, name)
	delete(c.reverseDeps, name)

	return nil
}

// checkCircularDependencies 检查循环依赖
func (c *Container) checkCircularDependencies() error {
	visited := make(map[string]bool)
	recStack := make(map[string]bool)
	path := []string{}

	var dfs func(node string) error
	dfs = func(node string) error {
		visited[node] = true
		recStack[node] = true
		path = append(path, node)

		for dep := range c.dependencies[node] {
			if c.componentTypes[dep] != nil { // 只检查已注册的依赖
				if recStack[dep] {
					// 找到循环依赖
					cycleStart := -1
					for i, p := range path {
						if p == dep {
							cycleStart = i
							break
						}
					}
					if cycleStart != -1 {
						cycle := append(path[cycleStart:], dep)
						return fmt.Errorf("circular dependency detected: %s", strings.Join(cycle, " -> "))
					}
				}
				if !visited[dep] {
					if err := dfs(dep); err != nil {
						return err
					}
				}
			}
		}

		recStack[node] = false
		path = path[:len(path)-1]
		return nil
	}

	for name := range c.components {
		if !visited[name] {
			if err := dfs(name); err != nil {
				return err
			}
		}
	}

	return nil
}

// getStartupOrder 获取启动顺序（拓扑排序）
func (c *Container) getStartupOrder() ([]string, error) {
	inDegree := make(map[string]int)
	graph := c.dependencies

	// 计算入度
	for node := range graph {
		inDegree[node] = 0
	}
	for node := range graph {
		for dep := range graph[node] {
			if c.components[dep] != nil {
				inDegree[node]++
			}
		}
	}

	// 找到所有入度为0的节点
	queue := []string{}
	for node, degree := range inDegree {
		if degree == 0 {
			queue = append(queue, node)
		}
	}

	result := []string{}
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		result = append(result, node)

		// 减少邻居的入度
		for neighbor := range c.reverseDeps[node] {
			if inDegree[neighbor] > 0 {
				inDegree[neighbor]--
				if inDegree[neighbor] == 0 {
					queue = append(queue, neighbor)
				}
			}
		}
	}

	// 检查是否有环
	if len(result) != len(c.components) {
		return nil, fmt.Errorf("circular dependency detected during startup order calculation")
	}

	return result, nil
}

// Initialize 初始化所有组件
func (c *Container) Initialize(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.initialized {
		return nil
	}

	startupOrder, err := c.getStartupOrder()
	if err != nil {
		return err
	}

	for _, name := range startupOrder {
		component := c.components[name]
		if err := component.Initialize(ctx, c); err != nil {
			return fmt.Errorf("failed to initialize component '%s': %w", name, err)
		}
	}

	c.initialized = true
	return nil
}

// Start 启动所有组件
func (c *Container) Start(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.initialized {
		if err := c.Initialize(ctx); err != nil {
			return err
		}
	}

	if c.running {
		return nil
	}

	startupOrder, err := c.getStartupOrder()
	if err != nil {
		return err
	}

	for _, name := range startupOrder {
		component := c.components[name]
		if err := component.Start(ctx); err != nil {
			return fmt.Errorf("failed to start component '%s': %w", name, err)
		}
	}

	c.running = true
	return nil
}

// Stop 停止所有组件
func (c *Container) Stop(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.running {
		return nil
	}

	c.running = false

	// 按照启动顺序的逆序停止组件
	startupOrder, err := c.getStartupOrder()
	if err != nil {
		return err
	}

	for i := len(startupOrder) - 1; i >= 0; i-- {
		name := startupOrder[i]
		component := c.components[name]
		if err := component.Stop(ctx); err != nil {
			log.Printf("Warning: failed to stop component '%s': %v", name, err)
		}
	}

	return nil
}

// ListComponents 列出所有组件
func (c *Container) ListComponents() []string {
	c.mu.RLock()
	defer c.mu.RUnlock()

	names := make([]string, 0, len(c.components))
	for name := range c.components {
		names = append(names, name)
	}
	return names
}

// GetDependencies 获取组件的依赖
func (c *Container) GetDependencies(name string) ([]string, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if _, exists := c.components[name]; !exists {
		return nil, fmt.Errorf("component '%s' not found", name)
	}

	deps := make([]string, 0, len(c.dependencies[name]))
	for dep := range c.dependencies[name] {
		deps = append(deps, dep)
	}
	return deps, nil
}

// GetDependents 获取依赖指定组件的组件
func (c *Container) GetDependents(name string) ([]string, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if _, exists := c.components[name]; !exists {
		return nil, fmt.Errorf("component '%s' not found", name)
	}

	dependents := make([]string, 0, len(c.reverseDeps[name]))
	for dep := range c.reverseDeps[name] {
		dependents = append(dependents, dep)
	}
	return dependents, nil
}

// ShutdownContext 获取关闭上下文
func (c *Container) ShutdownContext() context.Context {
	return c.shutdownCtx
}

// Shutdown 触发关闭
func (c *Container) Shutdown() {
	c.shutdownCancel()
}

// Wait 等待关闭完成
func (c *Container) Wait() {
	c.shutdownWg.Wait()
}
