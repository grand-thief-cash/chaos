// config/validator.go
package config

import (
	"fmt"
)

// Validator 配置验证器
type Validator struct{}

// NewValidator 创建配置验证器
func NewValidator() *Validator {
	return &Validator{}
}

// Validate 验证配置
func (v *Validator) Validate(config *AppConfig) error {
	if config == nil {
		return fmt.Errorf("config cannot be nil")
	}

	// 验证数据库配置
	if err := v.validateDatabase(&config.Database); err != nil {
		return fmt.Errorf("database config validation failed: %w", err)
	}

	// 验证服务器配置
	if err := v.validateServer(&config.Server); err != nil {
		return fmt.Errorf("server config validation failed: %w", err)
	}

	return nil
}

// validateDatabase 验证数据库配置
func (v *Validator) validateDatabase(config *DatabaseConfig) error {
	if config.MySQL != nil && config.MySQL.Enabled {
		if config.MySQL.Host == "" {
			return fmt.Errorf("mysql host cannot be empty")
		}
		if config.MySQL.Port <= 0 || config.MySQL.Port > 65535 {
			return fmt.Errorf("mysql port must be between 1 and 65535")
		}
	}

	if config.Redis != nil && config.Redis.Enabled {
		if config.Redis.Host == "" {
			return fmt.Errorf("redis host cannot be empty")
		}
		if config.Redis.Port <= 0 || config.Redis.Port > 65535 {
			return fmt.Errorf("redis port must be between 1 and 65535")
		}
	}

	return nil
}

// validateServer 验证服务器配置
func (v *Validator) validateServer(config *ServerConfig) error {
	if config.Gin != nil && config.Gin.Enabled {
		if config.Gin.Port <= 0 || config.Gin.Port > 65535 {
			return fmt.Errorf("gin port must be between 1 and 65535")
		}
	}

	if config.GRPC != nil && config.GRPC.Enabled {
		if config.GRPC.Port <= 0 || config.GRPC.Port > 65535 {
			return fmt.Errorf("grpc port must be between 1 and 65535")
		}
	}

	return nil
}
