// go
package grpc_server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/codes" // OTel status codes
	semconv "go.opentelemetry.io/otel/semconv/v1.37.0"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	grpcCodes "google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type GRPCServerComponent struct {
	*core.BaseComponent
	cfg       *Config
	container *core.Container
	server    *grpc.Server
	started   bool
	healthSrv *health.Server
}

func NewGRPCServerComponent(cfg *Config, c *core.Container) *GRPCServerComponent {
	return &GRPCServerComponent{
		BaseComponent: core.NewBaseComponent(
			consts.COMPONENT_GRPC_SERVER,
			consts.COMPONENT_LOGGING,
			consts.COMPONENT_TELEMETRY,
		),
		cfg:       cfg,
		container: c,
	}
}

func (gc *GRPCServerComponent) Start(ctx context.Context) error {
	if err := gc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if gc.cfg == nil || !gc.cfg.Enabled {
		return errors.New("grpc_server enabled flag mismatch")
	}

	unaryInts := []grpc.UnaryServerInterceptor{
		gc.otelTracingInterceptor(),
		gc.loggingInterceptor(),
		gc.recoveryInterceptor(),
	}
	opts := []grpc.ServerOption{
		grpc.MaxRecvMsgSize(gc.cfg.MaxRecvMsgSize),
		grpc.MaxSendMsgSize(gc.cfg.MaxSendMsgSize),
		grpc.ChainUnaryInterceptor(unaryInts...),
	}

	gc.server = grpc.NewServer(opts...)

	if gc.cfg.EnableHealth {
		gc.healthSrv = health.NewServer()
		healthpb.RegisterHealthServer(gc.server, gc.healthSrv)
		gc.healthSrv.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
	}
	if gc.cfg.EnableReflection {
		reflection.Register(gc.server)
	}

	for _, r := range snapshot() {
		if err := r(gc.server, gc.container); err != nil {
			return fmt.Errorf("grpc service register failed: %w", err)
		}
	}

	lis, err := net.Listen("tcp", gc.cfg.Address)
	if err != nil {
		return fmt.Errorf("listen failed: %w", err)
	}

	go func() {
		logging.Infof(ctx, "grpc_server listening on %s", gc.cfg.Address)
		if err := gc.server.Serve(lis); err != nil {
			logging.Errorf(ctx, "grpc_server serve error: %v", err)
		}
	}()

	gc.started = true
	return nil
}

func (gc *GRPCServerComponent) Stop(ctx context.Context) error {
	defer gc.BaseComponent.Stop(ctx)
	if !gc.started || gc.server == nil {
		return nil
	}
	deadline := time.Now().Add(gc.cfg.GracefulTimeout)
	done := make(chan struct{})
	go func() {
		gc.server.GracefulStop()
		close(done)
	}()
	select {
	case <-done:
		logging.Info(ctx, "grpc_server stopped gracefully")
	case <-ctx.Done():
		logging.Warn(ctx, "grpc_server stop context canceled, forcing")
		gc.server.Stop()
	case <-time.After(time.Until(deadline)):
		logging.Warn(ctx, "grpc_server graceful timeout exceeded, forcing")
		gc.server.Stop()
	}
	return nil
}

func (gc *GRPCServerComponent) HealthCheck() error {
	if err := gc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if !gc.started {
		return fmt.Errorf("grpc_server not started")
	}
	return nil
}

// OpenTelemetry tracing interceptor.
func (gc *GRPCServerComponent) otelTracingInterceptor() grpc.UnaryServerInterceptor {
	propagator := otel.GetTextMapPropagator()
	tracer := otel.Tracer("grpc.server")

	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		if md, ok := metadata.FromIncomingContext(ctx); ok {
			ctx = propagator.Extract(ctx, metadataCarrier{md})
		}

		service, method := splitFullMethod(info.FullMethod)
		ctx, span := tracer.Start(ctx, info.FullMethod, trace.WithSpanKind(trace.SpanKindServer))
		span.SetAttributes(
			semconv.RPCSystemGRPC,
			semconv.RPCService(service),
			semconv.RPCMethod(method),
		)
		defer span.End()

		resp, err := handler(ctx, req)
		if err != nil {
			span.RecordError(err)
			span.SetStatus(codes.Error, err.Error())
		} else {
			span.SetStatus(codes.Ok, "OK")
		}

		traceID := span.SpanContext().TraceID().String()
		_ = grpc.SetHeader(ctx, metadata.Pairs("trace_id", traceID))

		return resp, err
	}
}

func (gc *GRPCServerComponent) loggingInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
		start := time.Now()
		resp, err = handler(ctx, req)
		dur := time.Since(start)
		if err != nil {
			logging.Error(ctx, "grpc_access",
				zap.String("method", info.FullMethod),
				zap.Duration("dur", dur),
				zap.String("error", err.Error()),
			)
		} else {
			logging.Info(ctx, "grpc_access",
				zap.String("method", info.FullMethod),
				zap.Duration("dur", dur),
			)
		}
		return resp, err
	}
}

func (gc *GRPCServerComponent) recoveryInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
		defer func() {
			if r := recover(); r != nil {
				logging.Error(ctx, "panic recovered", zap.Any("panic", r), zap.String("method", info.FullMethod))
				err = status.Errorf(grpcCodes.Internal, "internal error")
			}
		}()
		return handler(ctx, req)
	}
}

type metadataCarrier struct{ metadata.MD }

func (mc metadataCarrier) Get(key string) string {
	values := mc.MD.Get(key)
	if len(values) == 0 {
		return ""
	}
	return values[0]
}
func (mc metadataCarrier) Set(key, value string) { mc.MD.Set(key, value) }
func (mc metadataCarrier) Keys() []string {
	keys := make([]string, 0, len(mc.MD))
	for k := range mc.MD {
		keys = append(keys, k)
	}
	return keys
}

func splitFullMethod(full string) (service, method string) {
	if full == "" {
		return "", ""
	}
	s := strings.TrimPrefix(full, "/")
	parts := strings.SplitN(s, "/", 2)
	if len(parts) == 2 {
		return parts[0], parts[1]
	}
	return s, ""
}
