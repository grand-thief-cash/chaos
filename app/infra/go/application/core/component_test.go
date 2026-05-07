package core

import (
	"context"
	"sync"
	"testing"
)

func TestBaseComponent_ConcurrentActiveAccess(t *testing.T) {
	bc := NewBaseComponent("test-comp")
	ctx := context.Background()

	// Start the component
	if err := bc.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	if !bc.IsActive() {
		t.Fatal("expected component to be active after Start")
	}

	// Hammer IsActive and SetActive from multiple goroutines to
	// verify no data race (go test -race will catch if atomic is missing).
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(3)
		go func() {
			defer wg.Done()
			_ = bc.IsActive()
		}()
		go func() {
			defer wg.Done()
			_ = bc.HealthCheck()
		}()
		go func() {
			defer wg.Done()
			bc.SetActive(true)
		}()
	}
	wg.Wait()

	// Stop and verify
	if err := bc.Stop(ctx); err != nil {
		t.Fatalf("Stop failed: %v", err)
	}
	if bc.IsActive() {
		t.Fatal("expected component to be inactive after Stop")
	}
}

func TestBaseComponent_ConcurrentDependencyAccess(t *testing.T) {
	bc := NewBaseComponent("test-comp", "depA")

	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(2)
		go func() {
			defer wg.Done()
			bc.AddDependencies("depX")
		}()
		go func() {
			defer wg.Done()
			_ = bc.Dependencies()
		}()
	}
	wg.Wait()

	deps := bc.Dependencies()
	if len(deps) < 1 {
		t.Fatal("expected at least 1 dependency")
	}
	// Verify returned deps is a copy (mutating it doesn't affect component)
	origLen := len(bc.Dependencies())
	deps = bc.Dependencies()
	deps = append(deps, "should_not_appear")
	if len(bc.Dependencies()) != origLen {
		t.Fatal("Dependencies() should return a copy, not a reference")
	}
}

func TestBaseComponent_HealthCheck(t *testing.T) {
	bc := NewBaseComponent("hc-comp")

	// Before start, HealthCheck should fail
	if err := bc.HealthCheck(); err == nil {
		t.Fatal("expected HealthCheck to fail before Start")
	}

	// After start, HealthCheck should pass
	if err := bc.Start(context.Background()); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	if err := bc.HealthCheck(); err != nil {
		t.Fatalf("expected HealthCheck to pass after Start, got %v", err)
	}

	// After stop, HealthCheck should fail again
	if err := bc.Stop(context.Background()); err != nil {
		t.Fatalf("Stop failed: %v", err)
	}
	if err := bc.HealthCheck(); err == nil {
		t.Fatal("expected HealthCheck to fail after Stop")
	}
}
