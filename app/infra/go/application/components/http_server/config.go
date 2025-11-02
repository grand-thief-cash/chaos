package http_server

import "time"

// HTTPServerConfig defines server settings.
type HTTPServerConfig struct {
	Enabled         bool          `yaml:"enabled" json:"enabled"`
	Address         string        `yaml:"address" json:"address"`                   // e.g. ":8080"
	ReadTimeout     time.Duration `yaml:"read_timeout" json:"read_timeout"`         // Max time the server spends reading the entire request (headers + body). Protects against slowloris clients.
	WriteTimeout    time.Duration `yaml:"write_timeout" json:"write_timeout"`       //Max time to finish writing the response. Prevents handlers from hanging while client reads slowly.
	IdleTimeout     time.Duration `yaml:"idle_timeout" json:"idle_timeout"`         // How long to keep idle keep-alive connections open (HTTP/1.1). Frees resources when clients go quiet.
	GracefulTimeout time.Duration `yaml:"graceful_timeout" json:"graceful_timeout"` // Upper bound during shutdown for in-flight requests to finish before forcing close.
	// Built-in endpoints
	EnableHealth bool `yaml:"enable_health" json:"enable_health"`
	EnablePprof  bool `yaml:"enable_pprof" json:"enable_pprof"`
	// ServiceName injected from APPInfo.APPName (not user configurable via YAML directly)
	ServiceName string `yaml:"-" json:"-"`
}
