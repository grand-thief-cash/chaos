// components/grpc_client/component.go
package grpc_client

import (
	"context"
	"crypto/tls"
	"fmt"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"

	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// GRPCClientComponent GRPC客户端管理组件
type GRPCClientComponent struct {
	*core.BaseComponent
	config            *GRPCClientsConfig
	clients           map[string]*grpc.ClientConn
	clientConfigs     map[string]*GRPCClientConfig
	healthCheckTicker *time.Ticker
	healthCheckStop   chan struct{}
	mutex             sync.RWMutex
}

// NewGRPCClientComponent 创建新的GRPC客户端组件
func NewGRPCClientComponent(config *GRPCClientsConfig) *GRPCClientComponent {
	deps := []string{}

	return &GRPCClientComponent{
		BaseComponent:   core.NewBaseComponent("grpc_clients", deps...),
		config:          config,
		clients:         make(map[string]*grpc.ClientConn),
		clientConfigs:   make(map[string]*GRPCClientConfig),
		healthCheckStop: make(chan struct{}),
	}
}

// Start 启动GRPC客户端组件
func (gc *GRPCClientComponent) Start(ctx context.Context) error {
	if err := gc.BaseComponent.Start(ctx); err != nil {
		return err
	}

	logging.Info(ctx, "Starting GRPC clients...")

	// 创建所有客户端连接
	for name, clientConfig := range gc.config.Clients {
		if err := gc.createClient(name, clientConfig); err != nil {
			gc.closeAllClients()
			return fmt.Errorf("failed to create client %s: %w", name, err)
		}
	}

	// 启动健康检查
	if gc.config.EnableHealthCheck {
		gc.startHealthCheck()
	}

	logging.Info(ctx, fmt.Sprintf("GRPC clients started, total: %d", len(gc.clients)))
	return nil
}

// Stop 停止GRPC客户端组件
func (gc *GRPCClientComponent) Stop(ctx context.Context) error {
	logging.Info(ctx, "Stopping GRPC clients...")

	// 停止健康检查
	if gc.healthCheckTicker != nil {
		gc.healthCheckTicker.Stop()
		close(gc.healthCheckStop)
	}

	// 关闭所有客户端连接
	gc.closeAllClients()

	logging.Info(ctx, "GRPC clients stopped")
	return gc.BaseComponent.Stop(ctx)
}

// HealthCheck 健康检查
func (gc *GRPCClientComponent) HealthCheck() error {
	if err := gc.BaseComponent.HealthCheck(); err != nil {
		return err
	}

	gc.mutex.RLock()
	defer gc.mutex.RUnlock()

	if len(gc.clients) == 0 {
		return nil // 没有客户端时也认为是健康的
	}

	healthyClients := 0
	for name, conn := range gc.clients {
		state := conn.GetState()
		if state == connectivity.Ready || state == connectivity.Idle {
			healthyClients++
		} else {
			logging.Info(context.Background(), fmt.Sprintf("GRPC client %s is not healthy, state: %v", name, state))
		}
	}

	if healthyClients == 0 {
		return fmt.Errorf("no healthy GRPC clients available")
	}

	return nil
}

// createClient 创建单个GRPC客户端
func (gc *GRPCClientComponent) createClient(name string, config *GRPCClientConfig) error {
	logging.Info(context.Background(), fmt.Sprintf("Creating GRPC client: %s -> %s:%d", name, config.Host, config.Port))

	// 设置默认值
	gc.setConfigDefaults(config)

	// 构建连接地址
	target := fmt.Sprintf("%s:%d", config.Host, config.Port)

	// 设置连接选项
	opts := []grpc.DialOption{
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(config.MaxReceiveMessageLength),
			grpc.MaxCallSendMsgSize(config.MaxSendMessageLength),
		),
	}

	// 添加keepalive选项
	if config.KeepaliveOptions != nil {
		kacp := keepalive.ClientParameters{
			Time:                config.KeepaliveOptions.Time,
			Timeout:             config.KeepaliveOptions.Timeout,
			PermitWithoutStream: config.KeepaliveOptions.PermitWithoutStream,
		}
		opts = append(opts, grpc.WithKeepaliveParams(kacp))
	}

	// 设置凭据
	if config.Secure {
		creds, err := gc.buildCredentials(config)
		if err != nil {
			return fmt.Errorf("failed to build credentials: %w", err)
		}
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	// 创建连接
	conn, err := grpc.Dial(target, opts...)
	if err != nil {
		return fmt.Errorf("failed to dial %s: %w", target, err)
	}

	gc.mutex.Lock()
	gc.clients[name] = conn
	gc.clientConfigs[name] = config
	gc.mutex.Unlock()

	logging.Info(context.Background(), fmt.Sprintf("GRPC client created successfully: %s", name))
	return nil
}

// setConfigDefaults 设置配置默认值
func (gc *GRPCClientComponent) setConfigDefaults(config *GRPCClientConfig) {
	if config.MaxReceiveMessageLength == 0 {
		config.MaxReceiveMessageLength = 4 * 1024 * 1024 // 4MB
	}
	if config.MaxSendMessageLength == 0 {
		config.MaxSendMessageLength = 4 * 1024 * 1024 // 4MB
	}
	if config.Timeout == 0 {
		config.Timeout = gc.config.DefaultTimeout
	}
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}
}

// buildCredentials 构建安全凭据
func (gc *GRPCClientComponent) buildCredentials(config *GRPCClientConfig) (credentials.TransportCredentials, error) {
	if config.CredentialsPath != "" {
		return credentials.NewClientTLSFromFile(config.CredentialsPath, "")
	}
	return credentials.NewTLS(&tls.Config{
		ServerName: config.Host,
	}), nil
}

// GetClient 获取指定名称的GRPC客户端连接
func (gc *GRPCClientComponent) GetClient(name string) (*grpc.ClientConn, error) {
	gc.mutex.RLock()
	defer gc.mutex.RUnlock()

	conn, exists := gc.clients[name]
	if !exists {
		return nil, fmt.Errorf("GRPC client not found: %s", name)
	}

	// 检查连接状态
	state := conn.GetState()
	if state == connectivity.Shutdown || state == connectivity.TransientFailure {
		return nil, fmt.Errorf("GRPC client %s is not available, state: %v", name, state)
	}

	return conn, nil
}

// AddClient 动态添加GRPC客户端
func (gc *GRPCClientComponent) AddClient(name string, config *GRPCClientConfig) error {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()

	// 如果客户端已存在，先关闭它
	if existingConn, exists := gc.clients[name]; exists {
		logging.Info(context.Background(), fmt.Sprintf("GRPC client %s already exists, replacing...", name))
		existingConn.Close()
	}

	return gc.createClient(name, config)
}

// RemoveClient 移除GRPC客户端
func (gc *GRPCClientComponent) RemoveClient(name string) error {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()

	conn, exists := gc.clients[name]
	if !exists {
		return fmt.Errorf("GRPC client not found: %s", name)
	}

	if err := conn.Close(); err != nil {
		logging.Error(context.Background(), fmt.Sprintf("Error closing GRPC client %s: %v", name, err))
	}

	delete(gc.clients, name)
	delete(gc.clientConfigs, name)

	logging.Info(context.Background(), fmt.Sprintf("GRPC client removed: %s", name))
	return nil
}

// startHealthCheck 启动健康检查
func (gc *GRPCClientComponent) startHealthCheck() {
	interval := gc.config.HealthCheckInterval
	if interval == 0 {
		interval = 60 * time.Second
	}

	gc.healthCheckTicker = time.NewTicker(interval)

	go func() {
		logging.Info(context.Background(), "GRPC health check started")
		for {
			select {
			case <-gc.healthCheckTicker.C:
				gc.performHealthCheck()
			case <-gc.healthCheckStop:
				logging.Info(context.Background(), "GRPC health check stopped")
				return
			}
		}
	}()
}

// performHealthCheck 执行健康检查
func (gc *GRPCClientComponent) performHealthCheck() {
	gc.mutex.RLock()
	clients := make(map[string]*grpc.ClientConn)
	for name, conn := range gc.clients {
		clients[name] = conn
	}
	gc.mutex.RUnlock()

	for name, conn := range clients {
		state := conn.GetState()
		if state == connectivity.TransientFailure || state == connectivity.Shutdown {
			logging.Info(context.Background(), fmt.Sprintf("GRPC client %s connection issue: %v", name, state))
			// 这里可以实现重连逻辑
		}
	}
}

// closeAllClients 关闭所有客户端连接
func (gc *GRPCClientComponent) closeAllClients() {
	gc.mutex.Lock()
	defer gc.mutex.Unlock()

	for name, conn := range gc.clients {
		logging.Info(context.Background(), fmt.Sprintf("Closing GRPC client: %s", name))
		if err := conn.Close(); err != nil {
			logging.Info(context.Background(), fmt.Sprintf("Error closing GRPC client %s: %v", name, err))
		}
	}

	gc.clients = make(map[string]*grpc.ClientConn)
	gc.clientConfigs = make(map[string]*GRPCClientConfig)
}
