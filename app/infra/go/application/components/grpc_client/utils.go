// components/grpc_client/utils.go
package grpc_client

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/grand-thief-cash/chaos/app/infra/infra_go/core"
)

// GetGRPCClient 从容器中获取GRPC客户端连接
func GetGRPCClient(container *core.Container, clientName string) (*grpc.ClientConn, error) {
	component, err := container.Resolve("grpc_clients")
	if err != nil {
		return nil, fmt.Errorf("GRPC clients component not found: %w", err)
	}

	grpcComponent, ok := component.(*GRPCClientComponent)
	if !ok {
		return nil, fmt.Errorf("invalid GRPC clients component type")
	}

	return grpcComponent.GetClient(clientName)
}

// CallWithRetry 带重试的GRPC调用
func CallWithRetry(ctx context.Context, conn *grpc.ClientConn, method string, req interface{}, resp interface{}, opts ...grpc.CallOption) error {
	policy := &RetryPolicy{
		MaxRetries:   3,
		InitialDelay: time.Second,
		MaxDelay:     10 * time.Second,
		Multiplier:   2.0,
	}

	return CallWithRetryPolicy(ctx, conn, method, req, resp, policy, opts...)
}

// CallWithRetryPolicy 使用指定重试策略的GRPC调用
func CallWithRetryPolicy(ctx context.Context, conn *grpc.ClientConn, method string, req interface{}, resp interface{}, policy *RetryPolicy, opts ...grpc.CallOption) error {
	var lastErr error
	delay := policy.InitialDelay

	for attempt := 0; attempt <= policy.MaxRetries; attempt++ {
		if attempt > 0 {
			// 等待重试延迟
			select {
			case <-time.After(delay):
			case <-ctx.Done():
				return ctx.Err()
			}

			// 计算下次延迟
			delay = time.Duration(float64(delay) * policy.Multiplier)
			if delay > policy.MaxDelay {
				delay = policy.MaxDelay
			}
		}

		// 执行GRPC调用
		err := conn.Invoke(ctx, method, req, resp, opts...)
		if err == nil {
			return nil
		}

		lastErr = err

		// 检查是否应该重试
		if !shouldRetry(err) || attempt == policy.MaxRetries {
			break
		}
	}

	return lastErr
}

// shouldRetry 判断错误是否应该重试
func shouldRetry(err error) bool {
	if err == nil {
		return false
	}

	st, ok := status.FromError(err)
	if !ok {
		return false
	}

	switch st.Code() {
	case codes.Unavailable, codes.DeadlineExceeded, codes.ResourceExhausted, codes.Aborted:
		return true
	default:
		return false
	}
}

// CreateMetadata 创建GRPC元数据
func CreateMetadata(traceID string) metadata.MD {
	md := metadata.New(map[string]string{
		"trace-id":       traceID,
		"user-agent":     "go-infra-grpc-client/1.0",
		"client-version": "1.0.0",
	})
	return md
}

// WithMetadata 为context添加元数据
func WithMetadata(ctx context.Context, md metadata.MD) context.Context {
	return metadata.NewOutgoingContext(ctx, md)
}