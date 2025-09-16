// go
// file: app/infra/go/application/components/grpc_server/registry.go
package grpc_server

import (
	"sync"

	"google.golang.org/grpc"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type ServiceRegistrar func(s *grpc.Server, c *core.Container) error

var (
	regMu      sync.RWMutex
	registrars []ServiceRegistrar
)

func RegisterService(fn ServiceRegistrar) {
	if fn == nil {
		return
	}
	regMu.Lock()
	registrars = append(registrars, fn)
	regMu.Unlock()
}

func snapshot() []ServiceRegistrar {
	regMu.RLock()
	cp := make([]ServiceRegistrar, len(registrars))
	copy(cp, registrars)
	regMu.RUnlock()
	return cp
}
