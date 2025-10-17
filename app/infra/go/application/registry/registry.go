package registry

import (
	"fmt"
	"reflect"
	"sort"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// NOTE: existing public API Register(name, fn) is kept for backward compatibility.
// New API RegisterWithDeps allows declaring inter-builder dependencies so that
// component build order can be deterministically topologically sorted.
// This ensures user-defined custom components that need other components' instances
// (e.g., to fetch a logger instance during construction) can rely on those builders
// having already run.

// BuilderFunc returns (enabled, component, error). If enabled=false component is ignored.
type BuilderFunc func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error)

// Builder wraps a builder function with its metadata / dependencies.
type Builder struct {
	Name string
	Deps []string // names of other builders this builder depends on (for build ordering)
	Fn   BuilderFunc
	Auto bool // true if registered via RegisterAuto (deps inferred from struct tags)
}

var builders = map[string]*Builder{}

// Register registers a component builder by name with no explicit build-time dependencies.
// Panics on duplicate to surface programming errors early.
func Register(name string, fn BuilderFunc) { RegisterWithDepsInternal(name, nil, fn, false) }

// RegisterAuto registers a builder without explicit build-time deps; intended for components
// whose dependencies are declared via struct tags and injected later by autowire.
func RegisterAuto(name string, fn BuilderFunc) { RegisterWithDepsInternal(name, nil, fn, true) }

// RegisterWithDeps registers a component builder with explicit dependencies.
// Dependencies are only used to order builder execution (topological sort) and do NOT
// automatically populate the Component.Dependencies() list; component authors should still
// set runtime dependencies inside their component implementation so that start/stop
// ordering is also enforced at runtime.
func RegisterWithDeps(name string, deps []string, fn BuilderFunc) {
	RegisterWithDepsInternal(name, deps, fn, false)
}

func RegisterWithDepsInternal(name string, deps []string, fn BuilderFunc, auto bool) {
	if _, exists := builders[name]; exists {
		panic("registry: duplicate builder registered for component " + name)
	}
	builders[name] = &Builder{Name: name, Deps: deps, Fn: fn, Auto: auto}
}

// BuildAndRegisterAll now performs a pre-build of auto builders to infer build-time dependencies
// from struct field tags (infra:"dep:<component>"). Only dependencies that correspond to other
// registered builder names are considered for ordering.
func BuildAndRegisterAll(cfg *config.AppConfig, c *core.Container) error {
	// First infer dependencies for auto builders that have no explicit deps.
	for _, b := range builders {
		if !b.Auto || len(b.Deps) > 0 {
			continue
		}
		// Pre-build component (ignore enabled flag; if disabled skip inference)
		enabled, comp, err := b.Fn(cfg, c)
		if err != nil || !enabled || comp == nil {
			continue // skip inference if build fails or disabled
		}
		deps := inferTagDependencies(comp)
		// Filter only those that are registered builder names (avoid spurious runtime-only deps)
		var filtered []string
		for _, d := range deps {
			if _, ok := builders[d]; ok {
				filtered = append(filtered, d)
			}
		}
		if len(filtered) > 0 {
			b.Deps = filtered
		}
	}
	ordered, err := sortBuilders()
	if err != nil {
		return err
	}
	for _, b := range ordered {
		enabled, comp, err := b.Fn(cfg, c)
		if err != nil {
			return fmt.Errorf("build component %s failed: %w", b.Name, err)
		}
		if !enabled || comp == nil {
			continue
		}
		if err := c.Register(b.Name, comp); err != nil {
			return fmt.Errorf("register component %s failed: %w", b.Name, err)
		}
	}
	// Apply user-declared runtime dependency extensions now that all components are registered.
	applyRuntimeDepExtensions(c)
	return nil
}

func inferTagDependencies(comp core.Component) []string {
	val := reflect.ValueOf(comp)
	if val.Kind() == reflect.Ptr {
		val = val.Elem()
	}
	if val.Kind() != reflect.Struct {
		return nil
	}
	typ := val.Type()
	seen := map[string]struct{}{}
	var deps []string
	for i := 0; i < typ.NumField(); i++ {
		f := typ.Field(i)
		if f.PkgPath != "" { // unexported
			continue
		}
		tag := f.Tag.Get("infra")
		if tag == "" || !strings.HasPrefix(tag, "dep:") {
			continue
		}
		name := strings.TrimSpace(strings.TrimPrefix(tag, "dep:"))
		if name == "" {
			continue
		}
		if strings.HasSuffix(name, "?") { // optional marker
			name = strings.TrimSuffix(name, "?")
		}
		if _, exists := seen[name]; exists {
			continue
		}
		seen[name] = struct{}{}
		deps = append(deps, name)
	}
	return deps
}

// List returns registered builder names (for debugging / tests)
func List() []string {
	keys := make([]string, 0, len(builders))
	for k := range builders {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// sortBuilders returns builders ordered topologically by Declared deps; if a dependency name
// is not itself a registered builder, it is ignored for build ordering (it may still be a
// runtime component dependency provided some other way). Cycles return an error.
func sortBuilders() ([]*Builder, error) {
	// Kahn's algorithm
	inDegree := map[string]int{}
	adj := map[string][]string{}
	// initialize
	for name, b := range builders {
		inDegree[name] = 0
		_ = b
	}
	for name, b := range builders {
		for _, dep := range b.Deps {
			if _, ok := builders[dep]; !ok {
				continue // ignore unknown builders for ordering purposes
			}
			adj[dep] = append(adj[dep], name)
			inDegree[name]++
		}
	}
	// queue of zero in-degree
	var zero []string
	for name, d := range inDegree {
		if d == 0 {
			zero = append(zero, name)
		}
	}
	sort.Strings(zero)
	ordered := make([]*Builder, 0, len(builders))
	for len(zero) > 0 {
		// pop first (lexicographically smallest for determinism)
		name := zero[0]
		zero = zero[1:]
		ordered = append(ordered, builders[name])
		for _, nxt := range adj[name] {
			inDegree[nxt]--
			if inDegree[nxt] == 0 {
				zero = append(zero, nxt)
			}
		}
		sort.Strings(zero)
	}
	if len(ordered) != len(builders) {
		// cycle exists; find participants
		var remaining []string
		for name, d := range inDegree {
			if d > 0 {
				remaining = append(remaining, name)
			}
		}
		sort.Strings(remaining)
		return nil, fmt.Errorf("registry: cyclic builder dependencies detected: %v", remaining)
	}
	return ordered, nil
}
