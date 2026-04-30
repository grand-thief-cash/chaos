package core

import (
	"context"
	"fmt"
	"testing"
)

func TestContainer_RegisterAndResolve(t *testing.T) {
	c := NewContainer()
	comp := NewBaseComponent("comp1")

	if err := c.Register("comp1", comp); err != nil {
		t.Fatalf("Register failed: %v", err)
	}

	// Duplicate registration
	if err := c.Register("comp1", comp); err == nil {
		t.Fatal("expected error on duplicate registration")
	}

	resolved, err := c.Resolve("comp1")
	if err != nil {
		t.Fatalf("Resolve failed: %v", err)
	}
	if resolved.Name() != "comp1" {
		t.Fatalf("expected name comp1, got %s", resolved.Name())
	}

	// Resolve non-existent
	_, err = c.Resolve("nonexistent")
	if err == nil {
		t.Fatal("expected error for non-existent component")
	}
}

func TestContainer_Replace(t *testing.T) {
	c := NewContainer()
	comp1 := NewBaseComponent("comp1")
	comp2 := NewBaseComponent("comp1")

	if err := c.Register("comp1", comp1); err != nil {
		t.Fatalf("Register failed: %v", err)
	}

	// Replace inactive component
	if err := c.Replace("comp1", comp2); err != nil {
		t.Fatalf("Replace failed: %v", err)
	}

	// Activate and try to replace
	comp2.SetActive(true)
	comp3 := NewBaseComponent("comp1")
	if err := c.Replace("comp1", comp3); err == nil {
		t.Fatal("expected error when replacing active component")
	}

	// Replace non-existent
	if err := c.Replace("nonexistent", comp3); err == nil {
		t.Fatal("expected error for replacing non-existent component")
	}
}

func TestContainer_SortComponentsByDependencies(t *testing.T) {
	c := NewContainer()
	compA := NewBaseComponent("a")
	compB := NewBaseComponent("b", "a")
	compC := NewBaseComponent("c", "b")

	_ = c.Register("a", compA)
	_ = c.Register("b", compB)
	_ = c.Register("c", compC)

	sorted, err := c.SortComponentsByDependencies()
	if err != nil {
		t.Fatalf("Sort failed: %v", err)
	}

	if len(sorted) != 3 {
		t.Fatalf("expected 3 components, got %d", len(sorted))
	}
	// a should come before b, b before c
	indexOf := func(name string) int {
		for i, comp := range sorted {
			if comp.Name() == name {
				return i
			}
		}
		return -1
	}
	if indexOf("a") >= indexOf("b") {
		t.Fatal("a should come before b")
	}
	if indexOf("b") >= indexOf("c") {
		t.Fatal("b should come before c")
	}
}

func TestContainer_CircularDependency(t *testing.T) {
	c := NewContainer()
	compA := NewBaseComponent("a", "b")
	compB := NewBaseComponent("b", "a")

	_ = c.Register("a", compA)
	_ = c.Register("b", compB)

	_, err := c.SortComponentsByDependencies()
	if err == nil {
		t.Fatal("expected circular dependency error")
	}
}

func TestContainer_ValidateDependencies_MissingDep(t *testing.T) {
	c := NewContainer()
	compA := NewBaseComponent("a", "missing")
	_ = c.Register("a", compA)

	_, err := c.ValidateDependencies()
	if err == nil {
		t.Fatal("expected missing dependency error")
	}
}

func TestContainer_ListRegistered(t *testing.T) {
	c := NewContainer()
	_ = c.Register("a", NewBaseComponent("a"))
	_ = c.Register("b", NewBaseComponent("b"))

	registered := c.ListRegistered()
	if len(registered) != 2 {
		t.Fatalf("expected 2 registered, got %d", len(registered))
	}
	// Mutating result shouldn't affect container
	delete(registered, "a")
	if len(c.ListRegistered()) != 2 {
		t.Fatal("ListRegistered should return a copy")
	}
}

func TestContainer_Config(t *testing.T) {
	c := NewContainer()
	c.SetConfig("key1", "value1")

	val, ok := c.GetConfig("key1")
	if !ok {
		t.Fatal("expected config key1 to exist")
	}
	if val != "value1" {
		t.Fatalf("expected value1, got %v", val)
	}

	_, ok = c.GetConfig("nonexistent")
	if ok {
		t.Fatal("expected nonexistent config to not exist")
	}
}

// mockFailComponent is a component whose Start always fails.
type mockFailComponent struct {
	*BaseComponent
	startErr error
}

func (m *mockFailComponent) Start(ctx context.Context) error {
	_ = m.BaseComponent.Start(ctx)
	return m.startErr
}

func TestLifecycleManager_StartAll_FailureCleanup(t *testing.T) {
	c := NewContainer()
	compA := NewBaseComponent("a")
	compB := &mockFailComponent{
		BaseComponent: NewBaseComponent("b", "a"),
		startErr:      fmt.Errorf("intentional start failure"),
	}

	_ = c.Register("a", compA)
	_ = c.Register("b", compB)

	lm := NewLifecycleManager(c)
	err := lm.StartAll(context.Background())
	if err == nil {
		t.Fatal("expected StartAll to fail")
	}

	// "a" should have been stopped during cleanup
	if compA.IsActive() {
		t.Fatal("component 'a' should have been stopped during cleanup")
	}
}

func TestLifecycleManager_StopAll_Idempotent(t *testing.T) {
	c := NewContainer()
	comp := NewBaseComponent("a")
	_ = c.Register("a", comp)

	lm := NewLifecycleManager(c)
	_ = lm.StartAll(context.Background())

	// StopAll should be idempotent
	ctx := context.Background()
	lm.StopAll(ctx)
	lm.StopAll(ctx) // second call should be a no-op
}
