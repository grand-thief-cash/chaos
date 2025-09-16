// go
// file: app/infra/go/application/components/grpc_server/config.go
package grpc_server

import "time"

type Config struct {
	Enabled          bool          `yaml:"enabled" json:"enabled"`
	Address          string        `yaml:"address" json:"address"` // ":50051"
	MaxRecvMsgSize   int           `yaml:"max_recv_msg_size" json:"max_recv_msg_size"`
	MaxSendMsgSize   int           `yaml:"max_send_msg_size" json:"max_send_msg_size"`
	GracefulTimeout  time.Duration `yaml:"graceful_timeout" json:"graceful_timeout"`
	EnableReflection bool          `yaml:"enable_reflection" json:"enable_reflection"`
	EnableHealth     bool          `yaml:"enable_health" json:"enable_health"`
}
