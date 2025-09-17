// file: internal/echo/echo_service.go
package services

import (
	"context"

	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
)

type EchoService struct {
	pb.UnimplementedEchoServiceServer
}

func (s *EchoService) Say(ctx context.Context, req *pb.EchoRequest) (*pb.EchoReply, error) {
	return &pb.EchoReply{Message: "Hi GRPC client, I received :" + req.Message}, nil
}
