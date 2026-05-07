package config

import (
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
)

var (
	bizConfig *BizConfig
)

func GetBizConfig() *BizConfig {
	return bizConfig
}

type WriteBufferConfig struct {
	Enabled              bool          `yaml:"enabled"`
	MaxBatchSize         int           `yaml:"max_batch_size"`
	FlushInterval        time.Duration `yaml:"flush_interval"`
	DirectFlushThreshold int           `yaml:"direct_flush_threshold"`
	ChannelSize          int           `yaml:"channel_size"`
	ShutdownTimeout      time.Duration `yaml:"shutdown_timeout"`
}

// DefaultWriteBufferConfig returns sensible defaults.
func DefaultWriteBufferConfig() WriteBufferConfig {
	return WriteBufferConfig{
		Enabled:              false,
		MaxBatchSize:         2000,
		FlushInterval:        3 * time.Second,
		DirectFlushThreshold: 500,
		ChannelSize:          8192,
		ShutdownTimeout:      10 * time.Second,
	}
}

type BizConfig struct {
	WriteBuffer WriteBufferConfig `yaml:"write_buffer"`
}

func init() {
	bizConfig = &BizConfig{
		WriteBuffer: DefaultWriteBufferConfig(),
	}
	app := application.GetApp()
	app.SetBizConfig(bizConfig)
}
