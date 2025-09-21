package http_client

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"sync"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type HTTPClientsComponent struct {
	*core.BaseComponent
	cfg     *HTTPClientsConfig
	mu      sync.RWMutex
	clients map[string]*InstrumentedClient
	defName string
}

func NewHTTPClientsComponent(cfg *HTTPClientsConfig) *HTTPClientsComponent {
	return &HTTPClientsComponent{
		BaseComponent: core.NewBaseComponent(
			consts.COMPONENT_HTTP_CLIENTS,
			consts.COMPONENT_LOGGING,   // require logging
			consts.COMPONENT_TELEMETRY, // soft dependency; if absent otelhttp falls back to no-op
		),
		cfg:     cfg,
		clients: map[string]*InstrumentedClient{},
	}
}

func (hc *HTTPClientsComponent) Start(ctx context.Context) error {
	if err := hc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if hc.cfg == nil || !hc.cfg.Enabled {
		return fmt.Errorf("http_clients disabled or missing config")
	}
	hc.cfg.applyDefaults()
	hc.defName = hc.cfg.Default

	for name, cCfg := range hc.cfg.Clients {
		underlying := &http.Transport{
			Proxy: http.ProxyFromEnvironment,
			DialContext: (&net.Dialer{
				Timeout:   5 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			MaxIdleConns:        cCfg.MaxIdleConns,
			MaxIdleConnsPerHost: cCfg.MaxIdleConnsPerHost,
			IdleConnTimeout:     cCfg.IdleConnTimeout,
			TLSHandshakeTimeout: 5 * time.Second,
		}

		rt := otelhttp.NewTransport(underlying)

		httpClient := &http.Client{
			Timeout:   cCfg.Timeout,
			Transport: rt,
		}

		ic := &InstrumentedClient{
			Name:           name,
			BaseURL:        cCfg.BaseURL,
			DefaultHeaders: cCfg.DefaultHeaders,
			Client:         httpClient,
			Retry:          cCfg.Retry,
			Underlying:     underlying,
		}
		hc.clients[name] = ic
	}

	SetGlobalHTTPClients(hc)
	logging.Info(ctx, "http_clients component started")
	return nil
}
func (hc *HTTPClientsComponent) Stop(ctx context.Context) error {
	defer hc.BaseComponent.Stop(ctx)
	hc.mu.RLock()
	for _, cli := range hc.clients {
		if cli != nil && cli.Underlying != nil {
			cli.Underlying.CloseIdleConnections()
		}
	}
	hc.mu.RUnlock()
	logging.Info(ctx, "http_clients component stopped")
	return nil
}
func (hc *HTTPClientsComponent) HealthCheck() error {
	if err := hc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	hc.mu.RLock()
	defer hc.mu.RUnlock()
	if len(hc.clients) == 0 {
		return fmt.Errorf("no http clients initialized")
	}
	return nil
}

func (hc *HTTPClientsComponent) Client(name string) (*InstrumentedClient, error) {
	hc.mu.RLock()
	defer hc.mu.RUnlock()
	if name == "" {
		name = hc.defName
	}
	cli, ok := hc.clients[name]
	if !ok {
		return nil, fmt.Errorf("http client %s not found", name)
	}
	return cli, nil
}

func (hc *HTTPClientsComponent) Default() (*InstrumentedClient, error) {
	return hc.Client(hc.defName)
}
