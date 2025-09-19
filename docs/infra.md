

# Infrastructure

## core
## hooks
## components

### Prometheus 

#### Configuration
1. enabled: Whether the Prometheus component starts (collector registry + HTTP exposure).
2. address / host / port: The listening address (e.g. :9090) for the metrics HTTP endpoint.
3. path: The HTTP route under which metrics are exposed (here /metrics).
4. namespace: Optional prefix for all metric names to avoid collisions.
5. subsystem: Optional second prefix (often the component/module name).
6. const_labels / labels: Key/value labels automatically attached to every metric.
7. pushgateway / push_interval: (Only if you support push mode) configuration to push metrics instead of (or in addition to) pull. If only path is shown, it just controls the URL where Prometheus scrapes.

#### Usage

prometheus.C() appears to be a global accessor returning the (already initialized) Prometheus component or a wrapper around a global registry.
NewCounter with []string{"route"} creates a counter vector; you must later use .WithLabelValues("xxx").Inc().
```golang
package demo

import (
	"context"

	appmetrics "github.com/grand-thief-cash/chaos/app/infra/go/application/components/prometheus"
)

var (
	reqCounter = appmetrics.C().NewCounter(
		"requests_total",
		"Total incoming requests",
		[]string{"route"},
	)
)

func HandleEcho(ctx context.Context, route string) {
	// Increment labeled counter
	reqCounter.WithLabelValues(route).Inc()
	// ... actual logic
}
```


# Common

