package registry_ext

import (
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/buffer"
	bizConfig "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/config"
)

func init() {
	// WriteBufferManager
	registry.RegisterAuto(func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		bc := bizConfig.GetBizConfig()
		bufCfg := buffer.Config{
			Enabled:              bc.WriteBuffer.Enabled,
			MaxBatchSize:         bc.WriteBuffer.MaxBatchSize,
			FlushInterval:        bc.WriteBuffer.FlushInterval,
			DirectFlushThreshold: bc.WriteBuffer.DirectFlushThreshold,
			ChannelSize:          bc.WriteBuffer.ChannelSize,
			ShutdownTimeout:      bc.WriteBuffer.ShutdownTimeout,
		}
		return true, buffer.NewWriteBufferManager(bufCfg), nil
	})
}
