// go
// file: app/infra/go/application/components/grpc_server/server_component.go
package grpc_server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"time"

	"github.com/google/uuid"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
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
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_GRPC_SERVER, consts.COMPONENT_LOGGING),
		cfg:           cfg,
		container:     c,
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
		gc.traceInterceptor(),
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

	// Register user services
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

// Interceptors
func (gc *GRPCServerComponent) traceInterceptor() grpc.UnaryServerInterceptor {
	traceMetaKeys := []string{
		"trace-id", "trace_id", "traceid", "x-trace-id", "request-id",
	}

	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		var traceID string

		if md, ok := metadata.FromIncomingContext(ctx); ok {
			for _, k := range traceMetaKeys {
				if vals := md.Get(k); len(vals) > 0 && vals[0] != "" {
					traceID = vals[0]
					break
				}
			}
		}

		if traceID == "" {
			traceID = uuid.New().String()
		}

		// Inject into context for logging component.
		ctx = context.WithValue(ctx, logging.TraceIDKey, traceID)

		// (Optional) return the trace-id to caller in response headers.
		_ = grpc.SetHeader(ctx, metadata.Pairs("trace-id", traceID))

		return handler(ctx, req)
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
				err = status.Errorf(codes.Internal, "internal error")
			}
		}()
		return handler(ctx, req)
	}
}
