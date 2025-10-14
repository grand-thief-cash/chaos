// go
package grpc_server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
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

	// Interceptor chain (order): recovery -> trace header injection -> logging
	unaryInts := []grpc.UnaryServerInterceptor{
		gc.recoveryInterceptor(),
		gc.traceHeaderInjectorInterceptor(),
		gc.loggingInterceptor(),
	}
	opts := []grpc.ServerOption{
		grpc.MaxRecvMsgSize(gc.cfg.MaxRecvMsgSize),
		grpc.MaxSendMsgSize(gc.cfg.MaxSendMsgSize),
		grpc.ChainUnaryInterceptor(unaryInts...),
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
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
	if !gc.started || gc.server == nil {
		return gc.BaseComponent.Stop(ctx)
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
	gc.started = false
	return gc.BaseComponent.Stop(ctx)
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

// loggingInterceptor now also logs grpc status code
func (gc *GRPCServerComponent) loggingInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
		start := time.Now()
		resp, err = handler(ctx, req)
		dur := time.Since(start)
		st := status.Code(err)
		if err != nil {
			logging.Error(ctx, "grpc_access",
				zap.String("method", info.FullMethod),
				zap.Duration("dur", dur),
				zap.String("grpc_status", st.String()),
				zap.String("error", err.Error()),
			)
		} else {
			logging.Info(ctx, "grpc_access",
				zap.String("method", info.FullMethod),
				zap.Duration("dur", dur),
				zap.String("grpc_status", st.String()),
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

// traceHeaderInjectorInterceptor injects a convenience 'trace_id' response header (non-standard) if a valid span is present.
func (gc *GRPCServerComponent) traceHeaderInjectorInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		resp, err := handler(ctx, req)
		if span := trace.SpanFromContext(ctx); span != nil {
			sc := span.SpanContext()
			if sc.IsValid() {
				_ = grpc.SetHeader(ctx, metadata.Pairs("trace_id", sc.TraceID().String()))
			}
		}
		return resp, err
	}
}
