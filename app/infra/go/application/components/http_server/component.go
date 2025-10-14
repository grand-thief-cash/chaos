// file: app/infra/go/application/components/http_server/http_component.go
package http_server

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/riandyrn/otelchi"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type HTTPServerComponent struct {
	*core.BaseComponent
	cfg       *HTTPServerConfig
	container *core.Container
	router    chi.Router
	server    *http.Server
	extras    []RouteRegisterFunc
	started   bool
}

func NewHTTPServerComponent(cfg *HTTPServerConfig, c *core.Container) *HTTPServerComponent {
	return &HTTPServerComponent{
		BaseComponent: core.NewBaseComponent(
			consts.COMPONENT_HTTP_SERVER,
			consts.COMPONENT_LOGGING,
			consts.COMPONENT_TELEMETRY,
		),
		cfg:       cfg,
		container: c,
	}
}

func (hc *HTTPServerComponent) AddRouteRegistrar(fn RouteRegisterFunc) error {
	if fn == nil {
		return nil
	}
	if hc.started {
		return fmt.Errorf("cannot register route: http_server already started (use BeforeStart hook)")
	}
	hc.extras = append(hc.extras, fn)
	return nil
}

func (hc *HTTPServerComponent) Router() chi.Router { return hc.router }

func (hc *HTTPServerComponent) Start(ctx context.Context) error {
	if err := hc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if hc.cfg == nil || !hc.cfg.Enabled {
		return errors.New("http_server component enabled flag mismatch")
	}

	hc.applyDefaults()

	hc.router = chi.NewRouter()
	hc.setupMiddlewares()

	if hc.cfg.EnableHealth {
		hc.router.Get("/healthz", hc.healthHandler)
	}

	if err := hc.registerAllRoutes(); err != nil {
		return err
	}

	hc.server = &http.Server{
		Addr:         hc.cfg.Address,
		ReadTimeout:  hc.cfg.ReadTimeout,
		WriteTimeout: hc.cfg.WriteTimeout,
		IdleTimeout:  hc.cfg.IdleTimeout,
		Handler:      hc.router,
	}

	go func() {
		logging.Infof(ctx, "http_server listening on %s", hc.cfg.Address)
		if err := hc.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logging.Errorf(ctx, "http_server server error: %v", err)
		}
	}()

	hc.started = true
	return nil
}

func (hc *HTTPServerComponent) Stop(ctx context.Context) error {
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
		return fmt.Errorf("http_server graceful shutdown failed: %w", err)
	}
	logging.Infof(ctx, "http_server server stopped")
	return nil
}

func (hc *HTTPServerComponent) HealthCheck() error {
	if err := hc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if !hc.started {
		return fmt.Errorf("http_server server not started")
	}
	return nil
}

func (hc *HTTPServerComponent) healthHandler(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}

func (hc *HTTPServerComponent) setupMiddlewares() {
	hc.router.Use(middleware.RealIP)
	hc.router.Use(middleware.Recoverer)
	hc.router.Use(middleware.Timeout(60 * time.Second))

	// OTel middleware: extracts W3C traceparent / tracestate and starts a server span.
	serviceName := hc.cfg.ServiceName
	if serviceName == "" { // fallback for backward compatibility
		serviceName = hc.cfg.Address
	}
	if tp := otel.GetTracerProvider(); tp != nil {
		// no-op
	}
	hc.router.Use(otelchi.Middleware(serviceName))

	// Access log with status + trace metadata; always return standard traceparent header (W3C) when span present.
	hc.router.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}

			// Fetch span context early (otelchi already ran) and set traceparent BEFORE handler writes headers
			if sc := trace.SpanContextFromContext(r.Context()); sc.IsValid() {
				w.Header().Set("traceparent", fmt.Sprintf("00-%s-%s-01", sc.TraceID().String(), sc.SpanID().String()))
			}

			next.ServeHTTP(sw, r)

			elapsed := time.Since(start)
			fields := []zap.Field{
				zap.String("method", r.Method),
				zap.String("path", r.URL.Path),
				zap.String("remote", r.RemoteAddr),
				zap.Int("status", sw.status),
				zap.Duration("dur", elapsed),
			}
			if sc := trace.SpanContextFromContext(r.Context()); sc.IsValid() {
				fields = append(fields, zap.String("trace_id", sc.TraceID().String()), zap.String("span_id", sc.SpanID().String()))
			}
			logging.Info(r.Context(), "http_access", fields...)
		})
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func (hc *HTTPServerComponent) registerAllRoutes() error {
	registrars := append(snapshot(), hc.extras...)
	for _, fn := range registrars {
		if err := fn(hc.router, hc.container); err != nil {
			return fmt.Errorf("route register failed: %w", err)
		}
	}
	return nil
}

func (hc *HTTPServerComponent) applyDefaults() {
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
