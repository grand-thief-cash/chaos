package main

import (
	"context"
	"fmt"
	"log"
	"time"

	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
	"google.golang.org/grpc"
)

func main() {
	// 连接到本地 gRPC 服务
	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure(), grpc.WithBlock())
	if err != nil {
		log.Fatalf("无法连接: %v", err)
	}
	defer conn.Close()

	c := pb.NewEchoServiceClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	// 调用 Echo 方法
	resp, err := c.Say(ctx, &pb.EchoRequest{Message: "hello grpc"})
	if err != nil {
		log.Fatalf("调用失败: %v", err)
	}
	fmt.Printf("收到响应: %s\n", resp.Message)
}
