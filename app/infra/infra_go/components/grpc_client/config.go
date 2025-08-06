// components/grpc_client/config.go
package grpc_client

import (
	"time"
)

// GRPCClientConfig 单个GRPC客户端配置
type GRPCClientConfig struct {
	Name                    string            `yaml:"name" json:"name"`
	Host                    string            `yaml:"host" json:"host"`
	Port                    int               `yaml:"port" json:"port"`
	Secure                  bool              `yaml:"secure" json:"secure"`
	CredentialsPath         string            `yaml:"credentials_path,omitempty" json:"credentials_path,omitempty"`
	MaxReceiveMessageLength int               `yaml:"max_receive_message_length" json:"max_receive_message_length"`
	MaxSendMessageLength    int               `yaml:"max_send_message_length" json:"max_send_message_length"`
	Compression             string            `yaml:"compression,omitempty" json:"compression,omitempty"`
	Timeout                 time.Duration     `yaml:"timeout" json:"timeout"`
	RetryPolicy             *RetryPolicy      `yaml:"retry_policy,omitempty" json:"retry_policy,omitempty"`
	KeepaliveOptions        *KeepaliveOptions `yaml:"keepalive_options,omitempty" json:"keepalive_options,omitempty"`
}

// GRPCClientsConfig 多GRPC客户端配置
type GRPCClientsConfig struct {
	Enabled             bool                         `yaml:"enabled" json:"enabled"`
	Clients             map[string]*GRPCClientConfig `yaml:"clients" json:"clients"`
	DefaultTimeout      time.Duration                `yaml:"default_timeout" json:"default_timeout"`
	EnableHealthCheck   bool                         `yaml:"enable_health_check" json:"enable_health_check"`
	HealthCheckInterval time.Duration                `yaml:"health_check_interval" json:"health_check_interval"`
}

// RetryPolicy 重试策略配置
type RetryPolicy struct {
	MaxRetries   int           `yaml:"max_retries" json:"max_retries"`
	InitialDelay time.Duration `yaml:"initial_delay" json:"initial_delay"`
	MaxDelay     time.Duration `yaml:"max_delay" json:"max_delay"`
	Multiplier   float64       `yaml:"multiplier" json:"multiplier"`
}

// KeepaliveOptions 保活选项配置
type KeepaliveOptions struct {
	Time                time.Duration `yaml:"time" json:"time"`
	Timeout             time.Duration `yaml:"timeout" json:"timeout"`
	PermitWithoutStream bool          `yaml:"permit_without_stream" json:"permit_without_stream"`
}
