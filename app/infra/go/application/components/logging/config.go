// components/logging/config.go
package logging

import "time"

// LoggingConfig 日志配置
type LoggingConfig struct {
	Enabled      bool          `yaml:"enabled" json:"enabled"`
	Level        string        `yaml:"level" json:"level"`
	Format       string        `yaml:"format" json:"format"`
	Output       string        `yaml:"output" json:"output"`
	FileConfig   *FileConfig   `yaml:"file_config,omitempty" json:"file_config,omitempty"`
	RotateConfig *RotateConfig `yaml:"rotate_config,omitempty" json:"rotate_config,omitempty"`
}

// FileConfig 文件输出配置
type FileConfig struct {
	Dir      string `yaml:"dir" json:"dir"`           // 日志文件目录
	Filename string `yaml:"filename" json:"filename"` // 日志文件名前缀，如 "app_name"
}

// RotateConfig 日志轮转配置
type RotateConfig struct {
	Enabled        bool          `yaml:"enabled" json:"enabled"`                 // 是否启用轮转
	RotateInterval time.Duration `yaml:"rotate_interval" json:"rotate_interval"` // 轮转时间间隔 (必须 >0 当 Enabled=true)
	MaxAge         time.Duration `yaml:"max_age" json:"max_age"`                 // 日志保留时间
	CleanupEnabled bool          `yaml:"cleanup_enabled" json:"cleanup_enabled"` // 是否启用清理
}
