// components/grpc_client/utils.go
package grpc_client

import (
	"context"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

//Details:
//GetGRPCClient: Thin convenience wrapper around resolving grpc_clients and calling GetClient(name). Adds little value; current code already does the explicit steps.
//CreateMetadata: Partially overlaps with the trace interceptor (trace-id injection). The extra keys (user-agent, client-version) are not consumed anywhere. Redundant now.
//CallWithRetry / CallWithRetryPolicy: Not used; they bypass generated stubs and call conn.Invoke directly. If you later adopt gRPC service config based retries or interceptor-based retries, these helpers are superseded.

//Remove if:
//You prefer lean code and there is no immediate plan for dynamic generic method invocation or custom metadata standardization.

//Keep (optional) if:
//You expect future generic RPC calls without generated stubs.
//You want a central place to evolve metadata (add auth tokens, locale, etc.).
//You will extend retry logic before adopting gRPC service config.
//How to confirm before deleting:
//
//
//Run: go build ./... (ensures no hidden references).
//If using vendoring (go mod vendor), remove the file from both the main path and any vendored copy (app/poc/infra/go/client/vendor/...) to avoid confusion.
//If you decide to delete: remove app/infra/go/application/components/grpc_client/utils.go.

// GetGRPCClient 从容器中获取GRPC客户端连接
func GetGRPCClient(container *core.Container, clientName string) (*grpc.ClientConn, error) {
	component, err := container.Resolve("grpc_clients")
	if err != nil {
		return nil, err
	}
	grpcComponent, ok := component.(*GRPCClientComponent)
	if !ok {
		return nil, err
	}
	return grpcComponent.GetClient(clientName)
}

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
			select {
			case <-time.After(delay):
			case <-ctx.Done():
				return ctx.Err()
			}
			delay = time.Duration(float64(delay) * policy.Multiplier)
			if delay > policy.MaxDelay {
				delay = policy.MaxDelay
			}
		}
		err := conn.Invoke(ctx, method, req, resp, opts...)
		if err == nil {
			return nil
		}
		lastErr = err
		if !shouldRetry(err) || attempt == policy.MaxRetries {
			break
		}
	}
	return lastErr
}

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
