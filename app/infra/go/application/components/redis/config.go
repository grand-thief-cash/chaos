// app/infra/go/application/components/redis/config.go
package redis

import "time"

// Mode: single | cluster | sentinel
type Config struct {
	Enabled bool   `yaml:"enabled" json:"enabled"`
	Mode    string `yaml:"mode" json:"mode"`

	Addresses      []string `yaml:"addresses" json:"addresses"`
	Username       string   `yaml:"username" json:"username"`
	Password       string   `yaml:"password" json:"password"`
	DB             int      `yaml:"db" json:"db"`
	SentinelMaster string   `yaml:"sentinel_master" json:"sentinel_master"`

	PoolSize     int `yaml:"pool_size" json:"pool_size"`
	MinIdleConns int `yaml:"min_idle_conns" json:"min_idle_conns"`

	// Renamed to align with redis.UniversalOptions
	ConnMaxLifetime time.Duration `yaml:"conn_max_lifetime" json:"conn_max_lifetime"`
	ConnMaxIdleTime time.Duration `yaml:"conn_max_idle_time" json:"conn_max_idle_time"`

	DialTimeout  time.Duration `yaml:"dial_timeout" json:"dial_timeout"`
	ReadTimeout  time.Duration `yaml:"read_timeout" json:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout" json:"write_timeout"`

	// Remove or ignore if library version lacks it
	// HealthCheckFreq time.Duration `yaml:"health_check_freq" json:"health_check_freq"`
}
