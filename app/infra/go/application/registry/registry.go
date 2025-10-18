package registry

import (
	"fmt"
	"reflect"
	"sort"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// BuilderFunc returns (enabled, component, error). enabled=false skips registration.
type BuilderFunc func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error)

// Builder holds metadata.
type Builder struct {
	Name       string         // final component name (may be inferred for auto builders)
	Fn         BuilderFunc    // build function
	Auto       bool           // auto builders: infer name + build-time deps from tags
	Deps       []string       // inferred build-time deps (auto) to order builders
	prebuilt   core.Component // cached component instance for name inference
	preEnabled bool           // cached enabled flag
}

var builders []*Builder

func findBuilder(name string) *Builder {
	for _, b := range builders {
		if b.Name == name {
			return b
		}
	}
	return nil
}

// Register registers a component builder with explicit name (no auto inference).
func Register(name string, fn BuilderFunc) {
	if name == "" {
		panic("registry: empty name in Register")
	}
	if findBuilder(name) != nil {
		panic("registry: duplicate builder name " + name)
	}
	builders = append(builders, &Builder{Name: name, Fn: fn, Auto: false})
}

// RegisterAuto registers a builder whose component name and build-time dependencies are inferred.
// The builder function MUST construct a component whose Name() returns a stable non-empty value.
func RegisterAuto(fn BuilderFunc) { builders = append(builders, &Builder{Auto: true, Fn: fn}) }

// BuildAndRegisterAll builds all registered builders applying:
// 1. For auto builders: pre-build to infer name and cache instance.
// 2. Infer build-time dependencies from struct tags for auto builders.
// 3. Topologically sort builders by inferred deps.
// 4. Build (reuse cached auto instance) and register components.
func BuildAndRegisterAll(cfg *config.AppConfig, c *core.Container) error {
	// Step 1: name inference for auto builders
	for _, b := range builders {
		if !b.Auto || b.Name != "" {
			continue
		}
		enabled, comp, err := b.Fn(cfg, c)
		if err != nil || comp == nil {
			b.preEnabled, b.prebuilt = false, nil
			continue
		}
		b.preEnabled, b.prebuilt = enabled, comp
		if !enabled {
			continue
		}
		name := comp.Name()
		if name == "" {
			return fmt.Errorf("auto builder produced unnamed component")
		}
		if existing := findBuilder(name); existing != nil && existing != b {
			return fmt.Errorf("duplicate inferred name: %s", name)
		}
		b.Name = name
	}
	// Step 2: infer deps for auto builders
	for _, b := range builders {
		if !b.Auto || len(b.Deps) > 0 || b.Name == "" {
			continue
		}
		comp := b.prebuilt
		if comp == nil || !b.preEnabled {
			continue
		}
		raw := inferTagDependencies(comp)
		var filtered []string
		for _, d := range raw {
			if findBuilder(d) != nil {
				filtered = append(filtered, d)
			}
		}
		b.Deps = filtered
	}
	// Step 3: topological sort
	ordered, err := topoSortBuilders(builders)
	if err != nil {
		return err
	}
	// Step 4: build & register
	for _, b := range ordered {
		var enabled bool
		var comp core.Component
		if b.Auto {
			// reuse cached instance (avoid double build). If disabled skip.
			enabled, comp = b.preEnabled, b.prebuilt
		} else {
			enabled, comp, err = b.Fn(cfg, c)
			if err != nil {
				return fmt.Errorf("build %s failed: %w", b.Name, err)
			}
		}
		if !enabled || comp == nil {
			continue
		}
		if err := c.Register(b.Name, comp); err != nil {
			return fmt.Errorf("register %s failed: %w", b.Name, err)
		}
	}
	applyRuntimeDepExtensions(c)
	return nil
}

// inferTagDependencies extracts component names from `infra:"dep:<name>"` tags.
func inferTagDependencies(comp core.Component) []string {
	v := reflect.ValueOf(comp)
	if v.Kind() == reflect.Ptr {
		v = v.Elem()
	}
	if v.Kind() != reflect.Struct {
		return nil
	}
	t := v.Type()
	seen := map[string]struct{}{}
	var out []string
	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		if f.PkgPath != "" {
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
		if strings.HasSuffix(name, "?") {
			name = strings.TrimSuffix(name, "?")
		}
		if _, exists := seen[name]; exists {
			continue
		}
		seen[name] = struct{}{}
		out = append(out, name)
	}
	return out
}

// topoSortBuilders orders builders by inferred deps (auto builders) + explicit names.
func topoSortBuilders(list []*Builder) ([]*Builder, error) {
	nameMap := map[string]*Builder{}
	inDeg := map[string]int{}
	adj := map[string][]string{}
	for _, b := range list {
		if b.Name != "" {
			nameMap[b.Name] = b
			inDeg[b.Name] = 0
		}
	}
	for _, b := range list {
		for _, d := range b.Deps {
			if _, ok := nameMap[d]; !ok {
				continue
			}
			adj[d] = append(adj[d], b.Name)
			inDeg[b.Name]++
		}
	}
	var zero []string
	for n, d := range inDeg {
		if d == 0 {
			zero = append(zero, n)
		}
	}
	sort.Strings(zero)
	var ordered []*Builder
	for len(zero) > 0 {
		n := zero[0]
		zero = zero[1:]
		ordered = append(ordered, nameMap[n])
		for _, nxt := range adj[n] {
			inDeg[nxt]--
			if inDeg[nxt] == 0 {
				zero = append(zero, nxt)
			}
		}
		sort.Strings(zero)
	}
	if len(ordered) != len(nameMap) {
		var cyc []string
		for n, d := range inDeg {
			if d > 0 {
				cyc = append(cyc, n)
			}
		}
		sort.Strings(cyc)
		return nil, fmt.Errorf("registry: cyclic builder deps: %v", cyc)
	}
	return ordered, nil
}
