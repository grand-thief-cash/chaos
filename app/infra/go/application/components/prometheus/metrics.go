package prometheus

import (
	"sync"

	"github.com/prometheus/client_golang/prometheus"
)

var (
	globalMu      sync.RWMutex
	globalMetrics *Component
)

func registerGlobal(c *Component) {
	globalMu.Lock()
	globalMetrics = c
	globalMu.Unlock()
}

func C() *Component {
	globalMu.RLock()
	defer globalMu.RUnlock()
	return globalMetrics
}

func Registry() *prometheus.Registry {
	if c := C(); c != nil {
		return c.registry
	}
	return nil
}
