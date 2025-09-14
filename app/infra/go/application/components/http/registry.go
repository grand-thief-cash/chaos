package http

import (
	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"sync"
)

// RouteRegisterFunc registers routes onto router; container provided for resolving components.
type RouteRegisterFunc func(r chi.Router, c *core.Container) error

var (
	registryMu sync.RWMutex
	registrars []RouteRegisterFunc
)

// RegisterRoutes (global) - simple style; call from controller init() or a setup function.
func RegisterRoutes(fn RouteRegisterFunc) {
	if fn == nil {
		return
	}
	registryMu.Lock()
	registrars = append(registrars, fn)
	registryMu.Unlock()
}

// snapshot returns a copy.
func snapshot() []RouteRegisterFunc {
	registryMu.RLock()
	cp := make([]RouteRegisterFunc, len(registrars))
	copy(cp, registrars)
	registryMu.RUnlock()
	return cp
}
