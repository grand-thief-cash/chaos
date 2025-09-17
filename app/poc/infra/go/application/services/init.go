// file: internal/echo/register.go
package services

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	pb "github.com/grand-thief-cash/chaos/app/infra/go/common/grpc_gen/poc"
	"google.golang.org/grpc"
)

func init() {
	fmt.Println("init executed: registering EchoService")
	grpc_server.RegisterService(func(s *grpc.Server, c *core.Container) error {
		pb.RegisterEchoServiceServer(s, &EchoService{})
		return nil
	})
}
