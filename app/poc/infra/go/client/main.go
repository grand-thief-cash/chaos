package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_client"
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
				if vals := headerMD.Get("trace_id"); len(vals) > 0 {
					fmt.Printf("Returned trace_id: %s\n", vals[0])
				} else {
					fmt.Println("No trace-id returned")
				}
			}
		}()
		return nil
	}, 100)

	// AfterStart hook: HTTP /ping via http_clients -> gRPC echo -> shutdown
	_ = app.AddHook("invoke_http_echo", hooks.AfterStart, func(ctx context.Context) error {
		go func() {
			rootCtx, rootSpan := otel.Tracer("poc.client").Start(context.Background(), "DemoCalls")
			defer rootSpan.End()

			// 1. HTTP /ping using http_clients component (client: server)
			func() {
				httpCtx, span := otel.Tracer("poc.client").Start(rootCtx, "HTTPPingCall")
				defer span.End()
				comp, err := app.GetComponent("http_clients")
				if err != nil {
					log.Printf("get http_clients component failed: %v", err)
					return
				}
				hcc := comp.(*http_client.HTTPClientsComponent)
				cli, err := hcc.Client("server")
				if err != nil {
					log.Printf("get http client 'server' failed: %v", err)
					return
				}
				var body string
				resp, err := cli.Get(httpCtx, "/ping", nil, nil, &body)
				if err != nil {
					log.Printf("HTTP /ping call error: %v", err)
					return
				}
				fmt.Printf("HTTP /ping status=%d body=%q traceparent=%s\n", resp.StatusCode, body, resp.Header.Get("traceparent"))
			}()

		}()
		return nil
	}, 100)

	_ = app.AddHook("app_shutdown", hooks.AfterStart, func(ctx context.Context) error {
		go func() {
			time.Sleep(5000 * time.Millisecond)
			app.Shutdown(context.Background())
		}()
		return nil
	}, 101)

	if err := app.Run(); err != nil {
		log.Fatalf("client app exited with error: %v", err)
	}

	if err := app.Run(); err != nil {
		log.Fatalf("client app exited with error: %v", err)
	}
}
