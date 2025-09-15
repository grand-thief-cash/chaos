// config/schema.go
package config

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
)

// AppConfig 应用程序配置结构
type AppConfig struct {
	APPInfo     *APPInfo                       `yaml:"app_info" json:"app_info"`
	Logging     *logging.LoggingConfig         `yaml:"logging" json:"logging"`
	GRPCClients *grpc_client.GRPCClientsConfig `yaml:"grpc_clients" json:"grpc_clients"`
	MySQL       *mysql.MySQLConfig             `yaml:"mysql" json:"mysql"`
	HTTPServer  *http_server.HTTPServerConfig  `yaml:"http_server" json:"http_server"`
}

type APPInfo struct {
	APPName string `yaml:"app_name" json:"app_name"`
	ENV     string `yaml:"env" json:"env"`
}
