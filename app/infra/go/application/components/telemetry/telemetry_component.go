// file: app/infra/go/application/components/telemetry/telemetry_component.go
package telemetry

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/exporters/stdout/stdoutmetric"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.37.0"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"google.golang.org/grpc"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type TelemetryComponent struct {
	*core.BaseComponent
	cfg           *Config
	tp            *sdktrace.TracerProvider
	mp            *sdkmetric.MeterProvider
	shutdownFuncs []func(context.Context) error
	started       bool
}

func NewTelemetryComponent(cfg *Config) *TelemetryComponent {
	return &TelemetryComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_TELEMETRY, consts.COMPONENT_LOGGING),
		cfg:           cfg,
	}
}

func (tc *TelemetryComponent) Start(ctx context.Context) error {
	if err := tc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if tc.cfg == nil || !tc.cfg.Enabled {
		return errors.New("telemetry disabled or missing config")
	}

	beforeRatio := tc.cfg.SampleRatio
	beforeExporter := tc.cfg.Exporter

	// apply defaults (no auto service name)
	cCopy := *tc.cfg
	_tcName := tc.cfg.ServiceName // keep for logging only
	cCopy.applyDefaults()
	// copy back mutated fields except service name (service name immutable here)
	tc.cfg.SampleRatio = cCopy.SampleRatio
	if tc.cfg.Exporter == "" {
		tc.cfg.Exporter = cCopy.Exporter
	}
	if tc.cfg.OTLP != nil && cCopy.OTLP != nil {
		tc.cfg.OTLP.Timeout = cCopy.OTLP.Timeout
	}

	if beforeRatio != tc.cfg.SampleRatio || beforeExporter != tc.cfg.Exporter {
		logging.Info(ctx, "telemetry config normalized",
			zap.Float64("sample_ratio_before", beforeRatio),
			zap.Float64("sample_ratio_after", tc.cfg.SampleRatio),
			zap.String("exporter_before", string(beforeExporter)),
			zap.String("exporter_after", string(tc.cfg.Exporter)),
			zap.String("service_name", _tcName),
		)
	}

	if tc.cfg.ServiceName == "" {
		return errors.New("telemetry service_name must be set (injected from APPInfo.app_name)")
	}

	res, err := resource.New(
		ctx,
		resource.WithFromEnv(),
		resource.WithProcess(),
		resource.WithOS(),
		resource.WithHost(),
		resource.WithAttributes(semconv.ServiceName(tc.cfg.ServiceName)),
	)
	if err != nil {
		return fmt.Errorf("resource init: %w", err)
	}

	if err := tc.initTracing(ctx, res); err != nil {
		return err
	}
	if err := tc.initMetrics(ctx, res); err != nil {
		return err
	}

	otel.SetTracerProvider(tc.tp)
	otel.SetMeterProvider(tc.mp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	tc.started = true
	logging.Info(ctx, "telemetry component started",
		zap.String("exporter", string(tc.cfg.Exporter)),
		zap.Float64("sample_ratio", tc.cfg.SampleRatio),
		zap.String("service_name", tc.cfg.ServiceName),
	)
	return nil
}
func (tc *TelemetryComponent) initTracing(ctx context.Context, res *resource.Resource) error {
	var (
		exp sdktrace.SpanExporter
		err error
	)

	switch tc.cfg.Exporter {
	case ExporterStdout:
		writer, errW := tc.stdoutWriter()
		if errW != nil {
			return errW
		}
		opts := []stdouttrace.Option{stdouttrace.WithWriter(writer)}
		if tc.cfg.StdoutPretty {
			opts = append(opts, stdouttrace.WithPrettyPrint())
		}
		exp, err = stdouttrace.New(opts...)
	case ExporterOTLP:
		if tc.cfg.OTLP == nil || tc.cfg.OTLP.Endpoint == "" {
			return errors.New("otlp exporter selected but otlp.endpoint empty")
		}
		opts := []otlptracegrpc.Option{
			otlptracegrpc.WithEndpoint(tc.cfg.OTLP.Endpoint),
			otlptracegrpc.WithTimeout(tc.cfg.otlpTimeout()),
		}
		if tc.cfg.OTLP.Insecure {
			opts = append(opts, otlptracegrpc.WithInsecure())
		} else {
			opts = append(opts, otlptracegrpc.WithDialOption(grpc.WithBlock()))
		}
		exp, err = otlptracegrpc.New(ctx, opts...)
	default:
		return fmt.Errorf("unsupported exporter: %s", tc.cfg.Exporter)
	}
	if err != nil {
		return fmt.Errorf("trace exporter init: %w", err)
	}

	sampler := sdktrace.ParentBased(sdktrace.TraceIDRatioBased(tc.cfg.SampleRatio))

	tc.tp = sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithSampler(sampler),
		sdktrace.WithResource(res),
	)

	tc.shutdownFuncs = append(tc.shutdownFuncs, func(c context.Context) error {
		c2, cancel := context.WithTimeout(c, 5*time.Second)
		defer cancel()
		return tc.tp.Shutdown(c2)
	})
	return nil
}

func (tc *TelemetryComponent) initMetrics(ctx context.Context, res *resource.Resource) error {
	var (
		err  error
		mExp sdkmetric.Exporter
	)

	switch tc.cfg.Exporter {
	case ExporterStdout:
		writer, errW := tc.stdoutWriter()
		if errW != nil {
			return errW
		}
		mExp, err = stdoutmetric.New(stdoutmetric.WithWriter(writer))
	case ExporterOTLP:
		if tc.cfg.OTLP == nil || tc.cfg.OTLP.Endpoint == "" {
			return errors.New("otlp exporter selected but otlp.endpoint empty (metrics)")
		}
		opts := []otlpmetricgrpc.Option{
			otlpmetricgrpc.WithEndpoint(tc.cfg.OTLP.Endpoint),
			otlpmetricgrpc.WithTimeout(tc.cfg.otlpTimeout()),
		}
		if tc.cfg.OTLP.Insecure {
			opts = append(opts, otlpmetricgrpc.WithInsecure())
		} else {
			opts = append(opts, otlpmetricgrpc.WithDialOption(grpc.WithBlock()))
		}
		mExp, err = otlpmetricgrpc.New(ctx, opts...)
	default:
		return fmt.Errorf("unsupported exporter: %s", tc.cfg.Exporter)
	}
	if err != nil {
		return fmt.Errorf("metric exporter init: %w", err)
	}

	reader := sdkmetric.NewPeriodicReader(
		mExp,
		sdkmetric.WithInterval(15*time.Second),
	)

	tc.mp = sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(reader),
	)

	tc.shutdownFuncs = append(tc.shutdownFuncs, func(c context.Context) error {
		c2, cancel := context.WithTimeout(c, 5*time.Second)
		defer cancel()
		return tc.mp.Shutdown(c2)
	})
	return nil
}

func (tc *TelemetryComponent) stdoutWriter() (io.Writer, error) {
	if tc.cfg.StdoutFile == "" {
		return os.Stdout, nil
	}
	f, err := os.OpenFile(tc.cfg.StdoutFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return nil, fmt.Errorf("open telemetry stdout file: %w", err)
	}
	tc.shutdownFuncs = append(tc.shutdownFuncs, func(ctx context.Context) error {
		return f.Close()
	})
	return f, nil
}

func (tc *TelemetryComponent) Stop(ctx context.Context) error {
	if !tc.started {
		return nil
	}
	var errs []error
	for i := len(tc.shutdownFuncs) - 1; i >= 0; i-- {
		if err := tc.shutdownFuncs[i](ctx); err != nil {
			errs = append(errs, err)
			logging.Warn(ctx, "telemetry shutdown func error", zap.Error(err))
		}
	}
	if err := tc.BaseComponent.Stop(ctx); err != nil {
		errs = append(errs, err)
		logging.Warn(ctx, "telemetry base stop error", zap.Error(err))
	}
	tc.started = false
	if len(errs) > 0 {
		return errors.Join(errs...)
	}
	logging.Info(ctx, "telemetry stopped gracefully")
	return nil
}

func (tc *TelemetryComponent) HealthCheck() error {
	if err := tc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if tc.tp == nil || tc.mp == nil {
		return errors.New("telemetry providers not initialized")
	}
	return nil
}

func (tc *TelemetryComponent) Tracer(name string) trace.Tracer {
	if tc.tp == nil {
		return otel.Tracer(name)
	}
	return tc.tp.Tracer(name)
}
