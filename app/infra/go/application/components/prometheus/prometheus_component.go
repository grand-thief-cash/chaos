package prometheus

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Component struct {
	*core.BaseComponent
	cfg       *Config
	server    *http.Server
	registry  *prometheus.Registry
	started   bool
	namespace string
	subsystem string
}

func NewComponent(cfg *Config) *Component {
	return &Component{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_PROMETHEUS, consts.COMPONENT_LOGGING),
		cfg:           cfg,
	}
}

func (c *Component) Start(ctx context.Context) error {
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	c.registry = prometheus.NewRegistry()
	if c.cfg.CollectGoMetrics {
		_ = c.registry.Register(prometheus.NewGoCollector())
	}
	if c.cfg.CollectProcess {
		_ = c.registry.Register(prometheus.NewProcessCollector(prometheus.ProcessCollectorOpts{}))
	}
	c.namespace = c.cfg.Namespace
	c.subsystem = c.cfg.Subsystem

	mux := http.NewServeMux()
	mux.Handle(c.cfg.Path, promhttp.HandlerFor(c.registry, promhttp.HandlerOpts{}))

	c.server = &http.Server{
		Addr:              c.cfg.Address,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logging.Infof(ctx, "prometheus metrics listening on %s%s", c.cfg.Address, c.cfg.Path)
		if err := c.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logging.Errorf(ctx, "prometheus server error: %v", err)
		}
	}()

	registerGlobal(c)
	c.started = true
	return nil
}

func (c *Component) Stop(ctx context.Context) error {
	defer c.BaseComponent.Stop(ctx)
	if !c.started || c.server == nil {
		return nil
	}
	shutdownCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := c.server.Shutdown(shutdownCtx); err != nil {
		return fmt.Errorf("prometheus server shutdown: %w", err)
	}
	logging.Info(ctx, "prometheus component stopped")
	return nil
}

func (c *Component) HealthCheck() error {
	if err := c.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if !c.started {
		return fmt.Errorf("prometheus not started")
	}
	return nil
}

// Helpers to build fully qualified name.
func (c *Component) fqName(name string) string {
	if c.namespace == "" && c.subsystem == "" {
		return name
	}
	if c.namespace != "" && c.subsystem != "" {
		return c.namespace + "_" + c.subsystem + "_" + name
	}
	if c.namespace != "" {
		return c.namespace + "_" + name
	}
	return c.subsystem + "_" + name
}

// Public metric registration shortcuts.
func (c *Component) NewCounter(name, help string, labels []string) *prometheus.CounterVec {
	cv := prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: c.fqName(name),
		Help: help,
	}, labels)
	_ = c.registry.Register(cv)
	return cv
}

func (c *Component) NewHistogram(name, help string, labels []string, buckets []float64) *prometheus.HistogramVec {
	hv := prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    c.fqName(name),
		Help:    help,
		Buckets: buckets,
	}, labels)
	_ = c.registry.Register(hv)
	return hv
}
