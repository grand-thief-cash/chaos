package autowire

// Lightweight single-field dependency injection using struct tags.
// Tag format supported: `infra:"dep:<component_name>"` or optional `infra:"dep:<component_name>?"`.
// A field tagged dep:<name> will be resolved from the container by component name and assigned.
// If the name ends with '?', missing component is ignored.
// Field must be exported and settable.
// After successful assignment, the target component's BaseComponent (if present) has the dependency appended
// so runtime start/stop ordering remains correct.

import (
	"fmt"
	"reflect"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type runtimeDepAdder interface {
	AddDependencies(...string)
}

// InjectAll scans all registered components in the container and injects tagged dependencies.
func InjectAll(c *core.Container) error {
	registered := c.ListRegistered()
	var errs []string
	for name, comp := range registered {
		if err := Inject(c, comp); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", name, err))
		}
	}
	if len(errs) > 0 {
		return fmt.Errorf("autowire errors: %s", strings.Join(errs, "; "))
	}
	return nil
}

// Inject performs injection for a single component.
func Inject(c *core.Container, comp core.Component) error {
	if comp == nil {
		return nil
	}
	val := reflect.ValueOf(comp)
	if val.Kind() != reflect.Ptr {
		return nil // need pointer to set fields
	}
	val = val.Elem()
	if val.Kind() != reflect.Struct {
		return nil
	}
	var adder runtimeDepAdder
	if a, ok := comp.(runtimeDepAdder); ok {
		adder = a
	}
	typ := val.Type()
	for i := 0; i < typ.NumField(); i++ {
		field := typ.Field(i)
		if field.PkgPath != "" { // unexported
			continue
		}
		tag := field.Tag.Get("infra")
		if tag == "" {
			continue
		}
		// only support single dep tag per requirement.
		if !strings.HasPrefix(tag, "dep:") {
			continue
		}
		name := strings.TrimPrefix(tag, "dep:")
		optional := false
		if strings.HasSuffix(name, "?") {
			optional = true
			name = strings.TrimSuffix(name, "?")
		}
		name = strings.TrimSpace(name)
		if name == "" {
			continue
		}
		resolved, err := c.Resolve(name)
		if err != nil {
			if optional {
				continue
			}
			return fmt.Errorf("resolve %s failed: %w", name, err)
		}
		fv := val.Field(i)
		if !fv.CanSet() {
			return fmt.Errorf("field %s not settable (must be exported)", field.Name)
		}
		if err := assignValue(fv, resolved); err != nil {
			return fmt.Errorf("assign %s -> field %s failed: %w", name, field.Name, err)
		}
		if adder != nil {
			adder.AddDependencies(name)
		}
	}
	return nil
}

func assignValue(dst reflect.Value, src interface{}) error {
	if !dst.CanSet() {
		return fmt.Errorf("destination not settable")
	}
	sv := reflect.ValueOf(src)
	// Interface field: ensure implementation
	if dst.Kind() == reflect.Interface {
		if sv.Type().Implements(dst.Type()) {
			dst.Set(sv)
			return nil
		}
		return fmt.Errorf("%s does not implement %s", sv.Type(), dst.Type())
	}
	// Direct assignable types
	if sv.Type().AssignableTo(dst.Type()) {
		dst.Set(sv)
		return nil
	}
	if sv.Type().ConvertibleTo(dst.Type()) {
		dst.Set(sv.Convert(dst.Type()))
		return nil
	}
	return fmt.Errorf("incompatible types: %s -> %s", sv.Type(), dst.Type())
}
