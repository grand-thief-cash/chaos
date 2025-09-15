// components/logging/factory.go
package logging

import (
	"fmt"
	"time"

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

	// 设置默认值
	f.setDefaults(loggingConfig)

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

	// 如果是文件输出但没有配置文件信息，设置默认值
	if cfg.Output != "stdout" && cfg.Output != "stderr" && cfg.FileConfig == nil {
		cfg.FileConfig = &FileConfig{
			Dir:      "./logs",
			Filename: "app",
		}
	}

	// 如果没有配置轮转，设置默认轮转配置
	if cfg.FileConfig != nil && cfg.RotateConfig == nil {
		cfg.RotateConfig = &RotateConfig{
			Enabled:        true,
			RotateDaily:    true,
			MaxAge:         15 * 24 * time.Hour, // 15天
			CleanupEnabled: true,
		}
	}
}
