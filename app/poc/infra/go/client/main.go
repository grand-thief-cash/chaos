package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"go.opentelemetry.io/otel"
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

	_ = app.AddHook("invoke_grpc_echo", hooks.AfterStart, func(ctx context.Context) error {
		go func() {
			// Start a span (optional) so trace propagates through OTel interceptors.
			ctx, span := otel.Tracer("poc.client").Start(context.Background(), "EchoRPC")
			defer span.End()
			rpcCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
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
			resp, err := client.Say(rpcCtx, &pb.EchoRequest{Message: "hello via rpc client"}, grpc.Header(&headerMD))
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

			time.Sleep(300 * time.Millisecond)
			app.Shutdown(context.Background())
		}()
		return nil
	}, 100)

	if err := app.Run(); err != nil {
		log.Fatalf("client app exited with error: %v", err)
	}
}

// testGRPCServer demonstrates a direct dial with OTel interceptors already applied in component code.
func testGRPCServer() {
	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure(), grpc.WithBlock())
	if err != nil {
		log.Fatalf("dial failed: %v", err)
	}
	defer conn.Close()

	c := pb.NewEchoServiceClient(conn)

	ctx, span := otel.Tracer("poc.client").Start(context.Background(), "EchoDirect")
	defer span.End()

	ctx, cancel := context.WithTimeout(ctx, time.Second)
	defer cancel()

	var headerMD metadata.MD
	resp, err := c.Say(ctx, &pb.EchoRequest{Message: "hello grpc"}, grpc.Header(&headerMD))
	if err != nil {
		log.Fatalf("rpc failed: %v", err)
	}

	fmt.Printf("响应: %s\n", resp.Message)
	if vals := headerMD.Get("trace-id"); len(vals) > 0 {
		fmt.Printf("服务器返回 trace-id: %s\n", vals[0])
	} else {
		fmt.Println("服务器未返回 trace-id")
	}
}
