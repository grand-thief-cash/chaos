// app/infra/go/application/components/redis/factory.go
package redis

import (
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	rc, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for redis component (*Config required)")
	}
	if rc == nil || !rc.Enabled {
		return nil, fmt.Errorf("redis component disabled")
	}
	setDefaults(rc)
	return NewRedisComponent(rc), nil
}

func setDefaults(c *Config) {
	if c == nil {
		return
	}

	// Mode
	if c.Mode == "" {
		c.Mode = "single"
	}

	// Addresses
	if len(c.Addresses) == 0 {

		switch c.Mode {
		case "single":
			c.Addresses = []string{"127.0.0.1:6379"}
		case "sentinel":
			c.Addresses = []string{"127.0.0.1:26379"}
		case "cluster":
			c.Addresses = []string{"127.0.0.1:7000", "127.0.0.1:7001", "127.0.0.1:7002"}
		}
	}

	// Pool sizing
	if c.PoolSize <= 0 {
		c.PoolSize = 20
	}
	if c.MinIdleConns < 0 {
		c.MinIdleConns = 0
	} else if c.MinIdleConns > c.PoolSize {
		c.MinIdleConns = c.PoolSize / 2
	}

	// Timeouts
	if c.DialTimeout <= 0 {
		c.DialTimeout = 5 * time.Second
	}
	if c.ReadTimeout <= 0 {
		c.ReadTimeout = 3 * time.Second
	}
	if c.WriteTimeout <= 0 {
		c.WriteTimeout = 3 * time.Second
	}

	// Connection lifetime / idle
	if c.ConnMaxIdleTime < 0 {
		c.ConnMaxIdleTime = 0
	}
	if c.ConnMaxLifetime < 0 {
		c.ConnMaxLifetime = 0
	}

	// DB
	if c.DB < 0 {
		c.DB = 0
	}

	// Sentinel sanity
	if c.Mode == "sentinel" && c.SentinelMaster == "" {
		// leave empty; validation during Start will raise error
	}
}
