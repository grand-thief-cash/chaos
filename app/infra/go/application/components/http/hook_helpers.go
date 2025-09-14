package http

import (
	"context"
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// BuildRegisterHook converts a RouteRegisterFunc into a HookFunc.
// Usage (after App created):
// app.AddHook("user_routes", hooks.BeforeStart, http.BuildRegisterHook(func(r chi.Router, c *core.Container) error {...}), 90)
func BuildRegisterHook(fn RouteRegisterFunc) func(ctx context.Context) error {
	return func(ctx context.Context) error {
		// We cannot access container from ctx; users capture it externally:
		val := ctx.Value("app_container")
		container, ok := val.(*core.Container)
		if !ok || container == nil {
			return fmt.Errorf("container not found in context (inject it before lifecycle start)")
		}
		compRaw, err := container.Resolve("http_server")
		if err != nil {
			return err
		}
		hc, ok := compRaw.(*HTTPComponent)
		if !ok {
			return fmt.Errorf("component http_server type mismatch")
		}
		// Temporarily create a lightweight router to collect – we just store fn and let Start run it.
		hc.AddRouteRegistrar(fn)
		return nil
	}
}

// (Optional) If you want a direct add without hook, call RegisterRoutes(fn).
