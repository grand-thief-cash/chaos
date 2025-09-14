package http

import "time"

// HTTPConfig defines server settings.
type HTTPConfig struct {
	Enabled         bool          `yaml:"enabled" json:"enabled"`
	Address         string        `yaml:"address" json:"address"` // e.g. ":8080"
	ReadTimeout     time.Duration `yaml:"read_timeout" json:"read_timeout"`
	WriteTimeout    time.Duration `yaml:"write_timeout" json:"write_timeout"`
	IdleTimeout     time.Duration `yaml:"idle_timeout" json:"idle_timeout"`
	GracefulTimeout time.Duration `yaml:"graceful_timeout" json:"graceful_timeout"`
	// Built‑in endpoints
	EnableHealth bool `yaml:"enable_health" json:"enable_health"`
	EnablePprof  bool `yaml:"enable_pprof" json:"enable_pprof"`
}
