package http

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type HTTPComponent struct {
	*core.BaseComponent
	cfg       *HTTPConfig
	container *core.Container
	router    chi.Router
	server    *http.Server
	extras    []RouteRegisterFunc // hook style registrations
	started   bool
}

// NewHTTPComponent creates the component (dependencies: logger, mysql optional).
func NewHTTPComponent(cfg *HTTPConfig, c *core.Container) *HTTPComponent {
	return &HTTPComponent{
		BaseComponent: core.NewBaseComponent("http_server", "logger", "mysql"),
		cfg:           cfg,
		container:     c,
	}
}

func (hc *HTTPComponent) AddRouteRegistrar(fn RouteRegisterFunc) {
	if fn == nil {
		return
	}
	hc.extras = append(hc.extras, fn)
}

func (hc *HTTPComponent) Router() chi.Router { return hc.router }

func (hc *HTTPComponent) Start(ctx context.Context) error {
	if err := hc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if hc.cfg == nil || !hc.cfg.Enabled {
		return errors.New("http component enabled flag mismatch")
	}

	hc.applyDefaults()

	hc.router = chi.NewRouter()
	hc.setupMiddlewares()

	// Built-in endpoints
	if hc.cfg.EnableHealth {
		hc.router.Get("/healthz", hc.healthHandler)
	}

	// Global + hook route registrars
	for _, fn := range snapshot() { // global registry
		if err := fn(hc.router, hc.container); err != nil {
			return fmt.Errorf("global route register failed: %w", err)
		}
	}
	for _, fn := range hc.extras { // hook injected
		if err := fn(hc.router, hc.container); err != nil {
			return fmt.Errorf("hook route register failed: %w", err)
		}
	}

	hc.server = &http.Server{
		Addr:         hc.cfg.Address,
		Handler:      hc.router,
		ReadTimeout:  hc.cfg.ReadTimeout,
		WriteTimeout: hc.cfg.WriteTimeout,
		IdleTimeout:  hc.cfg.IdleTimeout,
	}

	go func() {
		logging.Infof(ctx, "[http] listening on %s", hc.cfg.Address)
		if err := hc.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logging.Errorf(ctx, "[http] server error: %v", err)
		}
	}()

	hc.started = true
	return nil
}

func (hc *HTTPComponent) Stop(ctx context.Context) error {
	defer hc.BaseComponent.Stop(ctx)
	if !hc.started || hc.server == nil {
		return nil
	}
	timeout := hc.cfg.GracefulTimeout
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	stopCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	if err := hc.server.Shutdown(stopCtx); err != nil {
		return fmt.Errorf("http graceful shutdown failed: %w", err)
	}
	logging.Infof(ctx, "[http] server stopped")
	return nil
}

func (hc *HTTPComponent) HealthCheck() error {
	if err := hc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if !hc.started {
		return fmt.Errorf("http server not started")
	}
	return nil
}

func (hc *HTTPComponent) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}

func (hc *HTTPComponent) setupMiddlewares() {
	hc.router.Use(middleware.RequestID)
	hc.router.Use(middleware.RealIP)
	hc.router.Use(middleware.Recoverer)
	hc.router.Use(middleware.Timeout(60 * time.Second))
	// Custom logging middleware
	hc.router.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			ctx := context.WithValue(r.Context(), logging.TraceIDKey, middleware.GetReqID(r.Context()))
			next.ServeHTTP(w, r.WithContext(ctx))
			logging.Info(ctx, "http_access",
				zapString("method", r.Method),
				zapString("path", r.URL.Path),
				zapString("remote", r.RemoteAddr),
				zapString("dur", time.Since(start).String()))
		})
	})
}

// Helper to wrap simple string fields without importing zap in this file excessively.
func zapString(k, v string) loggingField {
	return loggingField{Key: k, Value: v}
}

// minimal adapter so we can pass fields through existing logger interface without exposing zap.Field directly here
type loggingField struct {
	Key, Value string
}

func (f loggingField) toZap() interface{} { return f }

// applyDefaults sets defaults.
func (hc *HTTPComponent) applyDefaults() {
	if hc.cfg.Address == "" {
		hc.cfg.Address = ":8080"
	}
	if hc.cfg.ReadTimeout == 0 {
		hc.cfg.ReadTimeout = 15 * time.Second
	}
	if hc.cfg.WriteTimeout == 0 {
		hc.cfg.WriteTimeout = 15 * time.Second
	}
	if hc.cfg.IdleTimeout == 0 {
		hc.cfg.IdleTimeout = 60 * time.Second
	}
	if hc.cfg.GracefulTimeout == 0 {
		hc.cfg.GracefulTimeout = 10 * time.Second
	}
}
