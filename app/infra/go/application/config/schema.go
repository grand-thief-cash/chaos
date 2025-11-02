// config/schema.go
package config

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/grpc_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_client"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/postgresgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/prometheus"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/redis"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/telemetry"
)

// AppConfig 应用程序配置结构
type AppConfig struct {
	APPInfo      *APPInfo                       `yaml:"app_info" json:"app_info"`
	BizConfig    any                            `yaml:"biz_config" json:"biz_config"`
	Logging      *logging.LoggingConfig         `yaml:"logging" json:"logging"`
	GRPCClients  *grpc_client.GRPCClientsConfig `yaml:"grpc_clients" json:"grpc_clients"`
	GRPCServer   *grpc_server.Config            `yaml:"grpc_server" json:"grpc_server"`
	MySQL        *mysql.MySQLConfig             `yaml:"mysql" json:"mysql"`
	MySQLGORM    *mysqlgorm.Config              `yaml:"mysql_gorm" json:"mysql_gorm"`
	PostgresGORM *postgresgorm.Config           `yaml:"postgres_gorm" json:"postgres_gorm"`
	HTTPServer   *http_server.HTTPServerConfig  `yaml:"http_server" json:"http_server"`
	HTTPClient   *http_client.HTTPClientsConfig `yaml:"http_clients" json:"http_clients"`
	Redis        *redis.Config                  `yaml:"redis" json:"redis"`
	Prometheus   *prometheus.Config             `yaml:"prometheus" json:"prometheus"`
	Telemetry    *telemetry.Config              `yaml:"telemetry" json:"telemetry"`
}

type APPInfo struct {
	APPName string `yaml:"app_name" json:"app_name"`
	ENV     string `yaml:"env" json:"env"`
}
