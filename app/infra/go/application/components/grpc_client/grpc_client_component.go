package grpc_client

import (
	"context"
	"crypto/tls"
	"fmt"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/metadata"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// GRPCClientComponent manages multiple gRPC client connections.
type GRPCClientComponent struct {
	*core.BaseComponent
	config            *GRPCClientsConfig
	clients           map[string]*grpc.ClientConn
	clientConfigs     map[string]*GRPCClientConfig
	healthCheckTicker *time.Ticker
	healthCheckStop   chan struct{}
	mutex             sync.RWMutex
}

// NewGRPCClientComponent creates a new component.
// Added dependency on logging to ensure logger is initialized first.
func NewGRPCClientComponent(config *GRPCClientsConfig) *GRPCClientComponent {
	return &GRPCClientComponent{
		BaseComponent:   core.NewBaseComponent("grpc_clients", consts.COMPONENT_LOGGING),
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
	logging.Info(ctx, "starting grpc clients")

	for name, clientConfig := range gc.config.Clients {
		gc.setConfigDefaults(clientConfig)
		gc.mutex.Lock()
		gc.clientConfigs[name] = clientConfig
		// Respect ConnectOnStart (default true)
		if !clientConfig.ConnectOnStart {
			logging.Info(ctx, fmt.Sprintf("grpc client %s deferred (lazy)", name))
			gc.mutex.Unlock()
			continue
		}
		gc.mutex.Unlock()

		if err := gc.createClient(name, clientConfig); err != nil {
			gc.closeAllClients()
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
	gc.closeAllClients()
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

// GetClient returns (and if necessary lazily creates) the named client connection.
func (gc *GRPCClientComponent) GetClient(name string) (*grpc.ClientConn, error) {
	if !gc.IsActive() {
		return nil, fmt.Errorf("grpc_clients component not active")
	}

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

	// Lazily create (double-checked locking)
	gc.mutex.Lock()
	defer gc.mutex.Unlock()
	if c2, ok := gc.clients[name]; ok && c2 != nil {
		return c2, nil
	}
	if err := gc.createClient(name, cfg); err != nil {
		return nil, err
	}
	return gc.clients[name], nil
}

// AddClient dynamically adds or replaces a client.
func (gc *GRPCClientComponent) AddClient(name string, config *GRPCClientConfig) error {
	gc.setConfigDefaults(config)
	gc.mutex.Lock()
	gc.clientConfigs[name] = config
	if existingConn, exists := gc.clients[name]; exists {
		existingConn.Close()
		delete(gc.clients, name)
	}
	gc.mutex.Unlock()
	if config.ConnectOnStart {
		return gc.createClient(name, config)
	}
	logging.Info(context.Background(), fmt.Sprintf("grpc client %s added (lazy, not connected yet)", name))
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
	conn.Close()
	delete(gc.clients, name)
	delete(gc.clientConfigs, name)
	logging.Info(context.Background(), fmt.Sprintf("grpc client removed: %s", name))
	return nil
}

func (gc *GRPCClientComponent) createClient(name string, config *GRPCClientConfig) error {
	logging.Info(context.Background(), fmt.Sprintf("dialing grpc client %s -> %s:%d", name, config.Host, config.Port))
	target := fmt.Sprintf("%s:%d", config.Host, config.Port)

	opts := []grpc.DialOption{
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(config.MaxReceiveMessageLength),
			grpc.MaxCallSendMsgSize(config.MaxSendMessageLength),
		),
	}

	if config.KeepaliveOptions != nil {
		kacp := keepalive.ClientParameters{
			Time:                config.KeepaliveOptions.Time,
			Timeout:             config.KeepaliveOptions.Timeout,
			PermitWithoutStream: config.KeepaliveOptions.PermitWithoutStream,
		}
		opts = append(opts, grpc.WithKeepaliveParams(kacp))
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
	opts = append(opts, grpc.WithChainUnaryInterceptor(gc.traceUnaryInterceptor()))

	conn, err := grpc.NewClient(target, opts...)
	if err != nil {
		return fmt.Errorf("dial %s: %w", target, err)
	}

	gc.mutex.Lock()
	gc.clients[name] = conn
	gc.mutex.Unlock()

	logging.Info(context.Background(), fmt.Sprintf("grpc client %s connected", name))
	return nil
}

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

func (gc *GRPCClientComponent) startHealthCheck() {
	interval := gc.config.HealthCheckInterval
	if interval == 0 {
		interval = 60 * time.Second
	}
	gc.healthCheckTicker = time.NewTicker(interval)
	go func() {
		logging.Info(context.Background(), "grpc health check started")
		for {
			select {
			case <-gc.healthCheckTicker.C:
				gc.performHealthCheck()
			case <-gc.healthCheckStop:
				logging.Info(context.Background(), "grpc health check stopped")
				return
			}
		}
	}()
}

func (gc *GRPCClientComponent) performHealthCheck() {
	gc.mutex.RLock()
	snapshot := make(map[string]*grpc.ClientConn, len(gc.clients))
	for k, v := range gc.clients {
		snapshot[k] = v
	}
	gc.mutex.RUnlock()

	for name, conn := range snapshot {
		state := conn.GetState()
		if state == connectivity.TransientFailure || state == connectivity.Shutdown {
			logging.Warn(context.Background(), fmt.Sprintf("grpc client %s state=%v", name, state))
		}
	}
}

func (gc *GRPCClientComponent) closeAllClients() {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()
	for name, conn := range gc.clients {
		_ = conn.Close()
		logging.Info(context.Background(), fmt.Sprintf("closed grpc client: %s", name))
	}
	gc.clients = make(map[string]*grpc.ClientConn)
}

// ADD method (place near other methods):
func (gc *GRPCClientComponent) traceUnaryInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{},
		cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {

		if traceID, ok := ctx.Value(consts.KEY_TraceID).(string); ok && traceID != "" {
			md, has := metadata.FromOutgoingContext(ctx)
			if !has {
				md = metadata.New(nil)
			} else {
				md = md.Copy()
			}
			md.Set("trace-id", traceID)
			ctx = metadata.NewOutgoingContext(ctx, md)
		}
		return invoker(ctx, method, req, reply, cc, opts...)
	}
}
