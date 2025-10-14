package grpc_client

import (
	"context"
	"crypto/tls"
	"fmt"
	"sync"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type GRPCClientComponent struct {
	*core.BaseComponent
	config            *GRPCClientsConfig
	clients           map[string]*grpc.ClientConn
	clientConfigs     map[string]*GRPCClientConfig
	healthCheckTicker *time.Ticker
	healthCheckStop   chan struct{}
	mutex             sync.RWMutex
	baseCtx           context.Context // root context captured at Start for internal ops
}

func NewGRPCClientComponent(config *GRPCClientsConfig) *GRPCClientComponent {
	return &GRPCClientComponent{
		// add telemetry dependency so tracer provider is ready before dialing
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_GRPC_CLIENTS,
			consts.COMPONENT_LOGGING,
			consts.COMPONENT_TELEMETRY),
		config:          config,
		clients:         make(map[string]*grpc.ClientConn),
		clientConfigs:   make(map[string]*GRPCClientConfig),
		healthCheckStop: make(chan struct{}),
	}
}

func (gc *GRPCClientComponent) Start(ctx context.Context) error {
	if err := gc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	gc.baseCtx = ctx
	logging.Info(ctx, "starting grpc clients")

	for name, clientConfig := range gc.config.Clients {
		gc.setConfigDefaults(clientConfig)
		gc.mutex.Lock()
		gc.clientConfigs[name] = clientConfig
		if !clientConfig.ConnectOnStart {
			logging.Info(ctx, fmt.Sprintf("grpc client %s deferred (lazy)", name))
			gc.mutex.Unlock()
			continue
		}
		gc.mutex.Unlock()

		if err := gc.createClient(ctx, name, clientConfig); err != nil {
			gc.closeAllClients(ctx)
			return fmt.Errorf("failed to create client %s: %w", name, err)
		}
	}

	if gc.config.EnableHealthCheck {
		gc.startHealthCheck()
	}

	logging.Info(ctx, fmt.Sprintf("grpc clients started, total connections: %d", len(gc.clients)))
	return nil
}

func (gc *GRPCClientComponent) Stop(ctx context.Context) error {
	logging.Info(ctx, "stopping grpc clients")
	if gc.healthCheckTicker != nil {
		gc.healthCheckTicker.Stop()
		close(gc.healthCheckStop)
	}
	gc.closeAllClients(ctx)
	return gc.BaseComponent.Stop(ctx)
}

func (gc *GRPCClientComponent) HealthCheck() error {
	if err := gc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	gc.mutex.RLock()
	defer gc.mutex.RUnlock()
	for name, conn := range gc.clients {
		state := conn.GetState()
		if !(state == connectivity.Ready || state == connectivity.Idle) {
			return fmt.Errorf("grpc client %s not healthy: %v", name, state)
		}
	}
	return nil
}

func (gc *GRPCClientComponent) GetClient(name string) (*grpc.ClientConn, error) {
	if !gc.IsActive() {
		return nil, fmt.Errorf("grpc_clients component not active")
	}
	// Fast read path
	gc.mutex.RLock()
	conn, exists := gc.clients[name]
	cfg, cfgExists := gc.clientConfigs[name]
	gc.mutex.RUnlock()
	if exists && conn != nil {
		state := conn.GetState()
		if state == connectivity.Shutdown || state == connectivity.TransientFailure {
			return nil, fmt.Errorf("grpc client %s unavailable state=%v", name, state)
		}
		return conn, nil
	}
	if !cfgExists {
		return nil, fmt.Errorf("grpc client config not found: %s", name)
	}
	// Dial outside lock
	if err := gc.createClient(gc.componentCtx(), name, cfg); err != nil {
		return nil, err
	}
	gc.mutex.RLock()
	ret := gc.clients[name]
	gc.mutex.RUnlock()
	return ret, nil
}

func (gc *GRPCClientComponent) AddClient(name string, config *GRPCClientConfig) error {
	gc.setConfigDefaults(config)
	gc.mutex.Lock()
	gc.clientConfigs[name] = config
	if existingConn, exists := gc.clients[name]; exists {
		_ = existingConn.Close()
		delete(gc.clients, name)
	}
	gc.mutex.Unlock()
	if config.ConnectOnStart {
		return gc.createClient(gc.componentCtx(), name, config)
	}
	logging.Info(gc.componentCtx(), fmt.Sprintf("grpc client %s added (lazy, not connected yet)", name))
	return nil
}

func (gc *GRPCClientComponent) RemoveClient(name string) error {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()
	conn, exists := gc.clients[name]
	if !exists {
		delete(gc.clientConfigs, name)
		return fmt.Errorf("grpc client not found: %s", name)
	}
	_ = conn.Close()
	delete(gc.clients, name)
	delete(gc.clientConfigs, name)
	logging.Info(gc.componentCtx(), fmt.Sprintf("grpc client removed: %s", name))
	return nil
}

// createClient now uses supplied ctx and installs logging interceptor + OTel stats handler
func (gc *GRPCClientComponent) createClient(ctx context.Context, name string, config *GRPCClientConfig) error {
	logging.Info(ctx, fmt.Sprintf("dialing grpc client %s -> %s:%d", name, config.Host, config.Port))
	target := fmt.Sprintf("%s:%d", config.Host, config.Port)

	unaryInts := []grpc.UnaryClientInterceptor{
		gc.loggingUnaryClientInterceptor(),
	}

	opts := []grpc.DialOption{
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(config.MaxReceiveMessageLength),
			grpc.MaxCallSendMsgSize(config.MaxSendMessageLength),
		),
		grpc.WithChainUnaryInterceptor(unaryInts...),
		grpc.WithStatsHandler(otelgrpc.NewClientHandler()), // tracing + metrics + propagation
	}

	if config.KeepaliveOptions != nil {
		opts = append(opts, grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                config.KeepaliveOptions.Time,
			Timeout:             config.KeepaliveOptions.Timeout,
			PermitWithoutStream: config.KeepaliveOptions.PermitWithoutStream,
		}))
	}

	if config.Secure {
		creds, err := gc.buildCredentials(config)
		if err != nil {
			return fmt.Errorf("build credentials: %w", err)
		}
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	var dialCtx context.Context
	var cancel context.CancelFunc
	if config.Timeout > 0 {
		dialCtx, cancel = context.WithTimeout(ctx, config.Timeout)
	} else {
		dialCtx, cancel = context.WithTimeout(ctx, 30*time.Second) // safety
	}
	defer cancel()
	conn, err := grpc.DialContext(dialCtx, target, opts...)
	if err != nil {
		return fmt.Errorf("grpc dial: %w", err)
	}
	gc.mutex.Lock()
	gc.clients[name] = conn
	gc.mutex.Unlock()

	logging.Info(ctx, fmt.Sprintf("grpc client %s connected", name))
	return nil
}

// loggingUnaryClientInterceptor logs request lifecycle with trace correlation.
func (gc *GRPCClientComponent) loggingUnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		start := time.Now()
		md, _ := metadata.FromOutgoingContext(ctx)
		err := invoker(ctx, method, req, reply, cc, opts...)
		dur := time.Since(start)
		st := status.Code(err)
		fields := []zap.Field{
			zap.String("method", method),
			zap.Duration("dur", dur),
			zap.String("grpc_status", st.String()),
		}
		if len(md) > 0 {
			fields = append(fields, zap.Int("md_keys", len(md)))
		}
		if err != nil {
			logging.Error(ctx, "grpc_client_call", append(fields, zap.String("error", err.Error()))...)
		} else {
			logging.Info(ctx, "grpc_client_call", fields...)
		}
		return err
	}
}

// componentCtx returns a context suitable for internal operations (never nil)
func (gc *GRPCClientComponent) componentCtx() context.Context {
	if gc.baseCtx != nil {
		return gc.baseCtx
	}
	return context.Background()
}

func (gc *GRPCClientComponent) startHealthCheck() {
	interval := gc.config.HealthCheckInterval
	if interval == 0 {
		interval = 60 * time.Second
	}
	gc.healthCheckTicker = time.NewTicker(interval)
	go func(base context.Context) {
		logging.Info(base, "grpc health check started")
		for {
			select {
			case <-gc.healthCheckTicker.C:
				gc.performHealthCheck(base)
			case <-gc.healthCheckStop:
				logging.Info(base, "grpc health check stopped")
				return
			}
		}
	}(gc.componentCtx())
}

func (gc *GRPCClientComponent) performHealthCheck(ctx context.Context) {
	gc.mutex.RLock()
	snapshot := make(map[string]*grpc.ClientConn, len(gc.clients))
	for k, v := range gc.clients {
		snapshot[k] = v
	}
	gc.mutex.RUnlock()

	for name, conn := range snapshot {
		state := conn.GetState()
		if state == connectivity.TransientFailure || state == connectivity.Shutdown {
			logging.Warn(ctx, fmt.Sprintf("grpc client %s state=%v", name, state))
		}
	}
}

func (gc *GRPCClientComponent) closeAllClients(ctx context.Context) {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()
	for name, conn := range gc.clients {
		_ = conn.Close()
		logging.Info(ctx, fmt.Sprintf("closed grpc client: %s", name))
	}
	gc.clients = make(map[string]*grpc.ClientConn)
}

// setConfigDefaults ensures per-client defaults, factoring component-level defaults
func (gc *GRPCClientComponent) setConfigDefaults(config *GRPCClientConfig) {
	if config.MaxReceiveMessageLength == 0 {
		config.MaxReceiveMessageLength = 4 * 1024 * 1024
	}
	if config.MaxSendMessageLength == 0 {
		config.MaxSendMessageLength = 4 * 1024 * 1024
	}
	if config.Timeout == 0 {
		if gc.config.DefaultTimeout > 0 {
			config.Timeout = gc.config.DefaultTimeout
		} else {
			config.Timeout = 30 * time.Second
		}
	}
}

func (gc *GRPCClientComponent) buildCredentials(config *GRPCClientConfig) (credentials.TransportCredentials, error) {
	if config.CredentialsPath != "" {
		return credentials.NewClientTLSFromFile(config.CredentialsPath, "")
	}
	return credentials.NewTLS(&tls.Config{ServerName: config.Host}), nil
}
