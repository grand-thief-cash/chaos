package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
)

func main() {
	if len(os.Args) < 3 {
		log.Fatalf("usage: client <env> <config_path>")
	}

	app := application.NewApp(os.Args[1], os.Args[2])

	// AfterStart hook: perform one Echo RPC via grpc client component then shutdown.
	_ = app.AddHook("invoke_grpc_echo", hooks.AfterStart, func(ctx context.Context) error {
		go func() {
			// Prepare trace context; interceptor will add it to outgoing metadata.
			traceID := "trace-client-demo-123"
			traceCtx := context.WithValue(context.Background(), consts.KEY_TraceID, traceID)
			// Optional per-RPC timeout.
			rpcCtx, cancel := context.WithTimeout(traceCtx, 3*time.Second)
			defer cancel()

			comp, err := app.GetComponent("grpc_clients")
			if err != nil {
				log.Printf("get grpc_clients component failed: %v", err)
				app.Shutdown(context.Background())
				return
			}
			gc := comp.(*grpc_client.GRPCClientComponent)

			conn, err := gc.GetClient("echo")
			if err != nil {
				log.Printf("get echo client failed: %v", err)
				app.Shutdown(context.Background())
				return
			}

			client := pb.NewEchoServiceClient(conn)
			var headerMD metadata.MD
			resp, err := client.Say(rpcCtx, &pb.EchoRequest{Message: "hello via component"}, grpc.Header(&headerMD))
			if err != nil {
				log.Printf("Echo RPC failed: %v", err)
			} else {
				fmt.Printf("Echo response: %s\n", resp.GetMessage())
				if vals := headerMD.Get("trace-id"); len(vals) > 0 {
					fmt.Printf("Returned trace-id: %s\n", vals[0])
				} else {
					fmt.Println("No trace-id returned")
				}
			}

			// Give a moment for logs to flush.
			time.Sleep(300 * time.Millisecond)
			app.Shutdown(context.Background())
		}()
		return nil
	}, 100)

	if err := app.Run(); err != nil {
		log.Fatalf("client app exited with error: %v", err)
	}
}

// Send a gRPC request to the server with custom trace-id in metadata
func testGRPCServer() {
	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure(), grpc.WithBlock())
	if err != nil {
		log.Fatalf("dial failed: %v", err)
	}
	defer conn.Close()

	c := pb.NewEchoServiceClient(conn)

	// self defined trace-id
	clientTraceID := "trace-demo-12345"

	// 出站 metadata
	md := metadata.New(map[string]string{
		"trace-id": clientTraceID,
	})
	ctx, cancel := context.WithTimeout(metadata.NewOutgoingContext(context.Background(), md), time.Second)
	defer cancel()

	// 捕获服务端返回的 header（包含服务器确认/生成的 trace-id）
	var headerMD metadata.MD
	resp, err := c.Say(ctx, &pb.EchoRequest{Message: "hello grpc"}, grpc.Header(&headerMD))
	if err != nil {
		log.Fatalf("rpc failed: %v", err)
	}

	fmt.Printf("响应: %s\n", resp.Message)

	// read trace-id
	if vals := headerMD.Get("trace-id"); len(vals) > 0 {
		fmt.Printf("服务器返回 trace-id: %s\n", vals[0])
	} else {
		fmt.Println("服务器未返回 trace-id")
	}
}
