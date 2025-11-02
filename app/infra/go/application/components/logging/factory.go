// components/logging/factory.go
package logging

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// Factory 日志组件工厂
type Factory struct{}

// NewFactory 创建日志组件工厂
func NewFactory() *Factory {
	return &Factory{}
}

// Create 创建日志组件实例
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	loggingConfig, ok := cfg.(*LoggingConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for logging component, expected *LoggingConfig")
	}

	if !loggingConfig.Enabled {
		return nil, fmt.Errorf("logging component is disabled")
	}

	f.setDefaults(loggingConfig)
	if err := f.validate(loggingConfig); err != nil {
		return nil, err
	}

	return NewLoggerComponent(loggingConfig), nil
}

// setDefaults 设置默认配置值
func (f *Factory) setDefaults(cfg *LoggingConfig) {
	if cfg.Level == "" {
		cfg.Level = "INFO"
	}
	if cfg.Format == "" {
		cfg.Format = "json"
	}
	if cfg.Output == "" {
		cfg.Output = "stdout"
	}

	if cfg.Output != "stdout" && cfg.Output != "stderr" && cfg.FileConfig == nil {
		cfg.FileConfig = &FileConfig{Dir: "./logs", Filename: "app"}
	}
}

// validate performs explicit validation rules without applying hidden defaults.
func (f *Factory) validate(cfg *LoggingConfig) error {
	if cfg.RotateConfig != nil && cfg.RotateConfig.Enabled {
		if cfg.RotateConfig.RotateInterval <= 0 {
			return fmt.Errorf("logging.rotate_config.rotate_interval must be > 0 when enabled=true")
		}
		if cfg.RotateConfig.MaxAge < 0 { // negative makes no sense
			return fmt.Errorf("logging.rotate_config.max_age must be >= 0")
		}
	}
	return nil
}
