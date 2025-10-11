package registry

import (
	"fmt"
	"sort"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// BuilderFunc returns (enabled, component, error). If enabled=false component is ignored.
type BuilderFunc func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error)

var builders = map[string]BuilderFunc{}

// Register registers a component builder by name. Panics on duplicate to surface programming errors early.
func Register(name string, fn BuilderFunc) {
	if _, exists := builders[name]; exists {
		panic("registry: duplicate builder registered for component " + name)
	}
	builders[name] = fn
}

// BuildAndRegisterAll iterates all registered builders (sorted by name for determinism),
// building and registering those whose builder reports enabled.
func BuildAndRegisterAll(cfg *config.AppConfig, c *core.Container) error {
	keys := make([]string, 0, len(builders))
	for k := range builders {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, name := range keys {
		fn := builders[name]
		enabled, comp, err := fn(cfg, c)
		if err != nil {
			return fmt.Errorf("build component %s failed: %w", name, err)
		}
		if !enabled || comp == nil {
			continue
		}
		if err := c.Register(name, comp); err != nil {
			return fmt.Errorf("register component %s failed: %w", name, err)
		}
	}
	return nil
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
