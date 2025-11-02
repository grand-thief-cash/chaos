// file: internal/echo/echo_service.go
package services

import (
	"context"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
)

type EchoService struct {
	pb.UnimplementedEchoServiceServer
	//MySQL *mysql.MysqlComponent
	//Redis *redis.RedisComponent
	// 其他依赖...
}

//func NewEchoService(mysql *mysql.MysqlComponent, redis *redis.RedisComponent) *EchoService {
//	return &EchoService{
//		//MySQL: mysql,
//		//Redis: redis,
//	}
//}

func NewEchoService() *EchoService {
	return &EchoService{
		//MySQL: mysql,
		//Redis: redis,
	}
}

func (s *EchoService) Say(ctx context.Context, req *pb.EchoRequest) (*pb.EchoReply, error) {
	logging.Info(ctx, "EchoService.Say called")

	return &pb.EchoReply{Message: "Hi GRPC client, I received :" + req.Message}, nil
}
