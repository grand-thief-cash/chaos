// hooks/hook.go
package hooks

import (
	"context"
	"fmt"
	"sort"
	"sync"
)

// HookFunc 钩子函数类型
type HookFunc func(ctx context.Context) error

// Phase 生命周期阶段
type Phase string

const (
	BeforeStart    Phase = "before_start"
	AfterStart     Phase = "after_start"
	BeforeShutdown Phase = "before_shutdown"
	AfterShutdown  Phase = "after_shutdown"
)

// Hook 钩子结构
type Hook struct {
	Name     string
	Phase    Phase
	Function HookFunc
	Priority int // 优先级，数值越小优先级越高
}

// Manager 钩子管理器
type Manager struct {
	hooks map[Phase][]*Hook
	mutex sync.RWMutex
}

// NewManager 创建新的钩子管理器
func NewManager() *Manager {
	return &Manager{
		hooks: make(map[Phase][]*Hook),
	}
}

// Register 注册钩子
func (m *Manager) Register(hook *Hook) error {
	if hook == nil {
		return fmt.Errorf("hook cannot be nil")
	}

	if hook.Function == nil {
		return fmt.Errorf("hook function cannot be nil")
	}

	if !isValidPhase(hook.Phase) {
		return fmt.Errorf("invalid hook phase: %s", hook.Phase)
	}

	m.mutex.Lock()
	defer m.mutex.Unlock()

	m.hooks[hook.Phase] = append(m.hooks[hook.Phase], hook)

	// 按优先级排序
	sort.Slice(m.hooks[hook.Phase], func(i, j int) bool {
		return m.hooks[hook.Phase][i].Priority < m.hooks[hook.Phase][j].Priority
	})

	return nil
}

// Execute 执行指定阶段的所有钩子
func (m *Manager) Execute(ctx context.Context, phase Phase) error {
	m.mutex.RLock()
	hooks := make([]*Hook, len(m.hooks[phase]))
	copy(hooks, m.hooks[phase])
	m.mutex.RUnlock()

	for _, hook := range hooks {
		if err := hook.Function(ctx); err != nil {
			return fmt.Errorf("hook %s failed: %w", hook.Name, err)
		}
	}

	return nil
}

// isValidPhase 检查阶段是否有效
func isValidPhase(phase Phase) bool {
	validPhases := []Phase{BeforeStart, AfterStart, BeforeShutdown, AfterShutdown}
	for _, p := range validPhases {
		if p == phase {
			return true
		}
	}
	return false
}
