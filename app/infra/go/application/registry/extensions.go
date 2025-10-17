package registry

import (
	"log"
	"sync"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// runtimeDepExtMap stores user-declared extra runtime dependency edges to be applied
// AFTER components are built & registered but BEFORE lifecycle StartAll sorts them.
// key: target component name -> slice of additional dependency component names.
var (
	runtimeDepExtMap = map[string][]string{}
	runtimeDepExtMu  sync.Mutex
)

// ExtendRuntimeDependencies allows framework users (typically inside their init() of a project
// specific package) to declare that component `target` should additionally depend on one or more
// other components `deps`. This affects ONLY runtime start/stop ordering (component.Dependencies()).
// It does NOT influence build order of builders (use RegisterWithDeps for that) and must be
// declared BEFORE registry.BuildAndRegisterAll is executed (usually early init time).
// Unknown target components are ignored when applied (a warning is logged).
func ExtendRuntimeDependencies(target string, deps ...string) {
	if target == "" || len(deps) == 0 {
		return
	}
	runtimeDepExtMu.Lock()
	defer runtimeDepExtMu.Unlock()
	current := runtimeDepExtMap[target]
	// simple append; duplicates not filtered to keep logic simple; lifecycle validation tolerates duplicates
	current = append(current, deps...)
	runtimeDepExtMap[target] = current
}

// applyRuntimeDepExtensions walks all registered components and if a component matches a target
// declared via ExtendRuntimeDependencies and it implements the optional interface { AddDependencies(...string) },
// it patches in the extra deps.
func applyRuntimeDepExtensions(c *core.Container) {
	runtimeDepExtMu.Lock()
	defer runtimeDepExtMu.Unlock()
	if len(runtimeDepExtMap) == 0 {
		return
	}
	for target, extra := range runtimeDepExtMap {
		comp, err := c.Resolve(target)
		if err != nil {
			log.Printf("registry: runtime dep extension target %s not registered (skipped): %v", target, err)
			continue
		}
		// minimal interface to avoid tying to concrete BaseComponent type
		if extender, ok := comp.(interface{ AddDependencies(...string) }); ok {
			extender.AddDependencies(extra...)
			log.Printf("registry: applied runtime dependency extension: %s += %v", target, extra)
		} else {
			log.Printf("registry: component %s does not support AddDependencies; extension skipped", target)
		}
	}
	// leave map intact (could allow diagnostics) or clear? choose to clear to avoid re-applying if BuildAndRegisterAll invoked twice
	runtimeDepExtMap = map[string][]string{}
}
