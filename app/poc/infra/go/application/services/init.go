// file: internal/echo/register.go
package services

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
	"google.golang.org/grpc"
)

func init() {
	grpc_server.RegisterService(func(s *grpc.Server, c *core.Container) error {
		//mysqlComp, _ := c.Resolve(consts.COMPONENT_MYSQL)
		//redisComp, _ := c.Resolve(consts.COMPONENT_REDIS)
		pb.RegisterEchoServiceServer(s, NewEchoService(
		//mysqlComp.(*mysql.MysqlComponent),
		//redisComp.(*redis.RedisComponent),
		))
		return nil
	})
}
