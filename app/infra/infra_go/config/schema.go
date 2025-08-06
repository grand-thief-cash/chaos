// config/schema.go
package config

import "github.com/grand-thief-cash/chaos/app/infra/infra_go/components/logging"

// AppConfig 应用程序配置结构
type AppConfig struct {
	Database DatabaseConfig        `yaml:"database" json:"database"`
	Server   ServerConfig          `yaml:"server" json:"server"`
	Logging  logging.LoggingConfig `yaml:"logging" json:"logging"`
	Tracing  TracingConfig         `yaml:"tracing" json:"tracing"`
	Monitor  MonitorConfig         `yaml:"monitor" json:"monitor"`
}

// DatabaseConfig 数据库配置
type DatabaseConfig struct {
	MySQL *MySQLConfig `yaml:"mysql,omitempty" json:"mysql,omitempty"`
	Redis *RedisConfig `yaml:"redis,omitempty" json:"redis,omitempty"`
}

// MySQLConfig MySQL配置
type MySQLConfig struct {
	Enabled  bool   `yaml:"enabled" json:"enabled"`
	Host     string `yaml:"host" json:"host"`
	Port     int    `yaml:"port" json:"port"`
	Username string `yaml:"username" json:"username"`
	Password string `yaml:"password" json:"password"`
	Database string `yaml:"database" json:"database"`
}

// RedisConfig Redis配置
type RedisConfig struct {
	Enabled  bool   `yaml:"enabled" json:"enabled"`
	Host     string `yaml:"host" json:"host"`
	Port     int    `yaml:"port" json:"port"`
	Password string `yaml:"password" json:"password"`
	DB       int    `yaml:"db" json:"db"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Gin  *GinConfig  `yaml:"gin,omitempty" json:"gin,omitempty"`
	GRPC *GRPCConfig `yaml:"grpc,omitempty" json:"grpc,omitempty"`
}

// GinConfig Gin服务器配置
type GinConfig struct {
	Enabled bool   `yaml:"enabled" json:"enabled"`
	Port    int    `yaml:"port" json:"port"`
	Mode    string `yaml:"mode" json:"mode"`
}

// GRPCConfig gRPC服务器配置
type GRPCConfig struct {
	Enabled bool `yaml:"enabled" json:"enabled"`
	Port    int  `yaml:"port" json:"port"`
}

// TracingConfig 链路追踪配置
type TracingConfig struct {
	Enabled bool `yaml:"enabled" json:"enabled"`
}

// MonitorConfig 监控配置
type MonitorConfig struct {
	Enabled bool `yaml:"enabled" json:"enabled"`
}
