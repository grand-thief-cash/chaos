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
func (v *Validator) ValidateAppConfig(config *AppConfig) error {
	if config == nil {
		return fmt.Errorf("config cannot be nil")
	}
	return nil
}

func (v *Validator) validateConfigFilePath(env string, path string) error {
	if path == "" {
		return fmt.Errorf("config file path cannot be empty")
	}
	if len(path) > 255 {
		return fmt.Errorf("config file path is too long")
	}

	// 验证config file 存在
	if !fileExists(path) {
		return fmt.Errorf("config file does not exist: %s", path)
	}

	if v.validateEnv() != nil {
		return fmt.Errorf("Running environment is not valid: %s", env)
	}
	return nil
}

// This is a placeholder for environment validation logic
func (v *Validator) validateEnv() error {
	return nil
}
