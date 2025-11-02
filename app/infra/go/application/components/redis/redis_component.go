// app/infra/go/application/components/redis/redis_component.go
package redis

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type RedisComponent struct {
	*core.BaseComponent
	cfg    *Config
	client redis.UniversalClient
}

func NewRedisComponent(cfg *Config) *RedisComponent {
	return &RedisComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_REDIS, consts.COMPONENT_LOGGING),
		cfg:           cfg,
	}
}

func (rc *RedisComponent) Start(ctx context.Context) error {
	if err := rc.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if rc.cfg == nil {
		return errors.New("redis config nil")
	}
	if len(rc.cfg.Addresses) == 0 {
		return fmt.Errorf("redis addresses empty")
	}

	opts := &redis.UniversalOptions{
		Addrs:        rc.cfg.Addresses,
		DB:           rc.cfg.DB,
		Username:     rc.cfg.Username,
		Password:     rc.cfg.Password,
		MasterName:   rc.cfg.SentinelMaster,
		PoolSize:     rc.cfg.PoolSize,
		MinIdleConns: rc.cfg.MinIdleConns,

		DialTimeout:  rc.cfg.DialTimeout,
		ReadTimeout:  rc.cfg.ReadTimeout,
		WriteTimeout: rc.cfg.WriteTimeout,

		ConnMaxLifetime: rc.cfg.ConnMaxLifetime,
		ConnMaxIdleTime: rc.cfg.ConnMaxIdleTime,
	}

	switch strings.ToLower(rc.cfg.Mode) {
	case "single", "cluster", "sentinel":
		if rc.cfg.Mode == "sentinel" && rc.cfg.SentinelMaster == "" {
			return fmt.Errorf("sentinel mode requires sentinel_master")
		}
	default:
		return fmt.Errorf("unknown redis mode: %s", rc.cfg.Mode)
	}

	rc.client = redis.NewUniversalClient(opts)

	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := rc.ping(pingCtx); err != nil {
		_ = rc.client.Close()
		rc.client = nil
		return fmt.Errorf("redis ping failed: %w", err)
	}

	logging.Info(ctx, "redis component started",
		zap.String("mode", rc.cfg.Mode),
		zap.Strings("addrs", rc.cfg.Addresses),
	)
	return nil
}
func (rc *RedisComponent) Stop(ctx context.Context) error {
	defer rc.BaseComponent.Stop(ctx)
	if rc.client != nil {
		_ = rc.client.Close()
		logging.Info(ctx, "redis component stopped")
	}
	return nil
}

func (rc *RedisComponent) HealthCheck() error {
	if err := rc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if rc.client == nil {
		return fmt.Errorf("redis client nil")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return rc.ping(ctx)
}

func (rc *RedisComponent) ping(ctx context.Context) error {
	if rc.client == nil {
		return errors.New("no client")
	}
	_, err := rc.client.Ping(ctx).Result()
	return err
}

func (rc *RedisComponent) Client() redis.UniversalClient {
	return rc.client
}
