package http_client

import "time"

type RetryConfig struct {
	Enabled           bool          `yaml:"enabled" json:"enabled"`
	MaxAttempts       int           `yaml:"max_attempts" json:"max_attempts"`
	InitialBackoff    time.Duration `yaml:"initial_backoff" json:"initial_backoff"`
	MaxBackoff        time.Duration `yaml:"max_backoff" json:"max_backoff"`
	BackoffMultiplier float64       `yaml:"backoff_multiplier" json:"backoff_multiplier"`
}

type HTTPClientConfig struct {
	BaseURL             string            `yaml:"base_url" json:"base_url"`
	Timeout             time.Duration     `yaml:"timeout" json:"timeout"`
	MaxIdleConns        int               `yaml:"max_idle_conns" json:"max_idle_conns"`
	MaxIdleConnsPerHost int               `yaml:"max_idle_conns_per_host" json:"max_idle_conns_per_host"`
	IdleConnTimeout     time.Duration     `yaml:"idle_conn_timeout" json:"idle_conn_timeout"`
	DefaultHeaders      map[string]string `yaml:"default_headers" json:"default_headers"`
	Retry               *RetryConfig      `yaml:"retry" json:"retry"`
}

type HTTPClientsConfig struct {
	Enabled bool                         `yaml:"enabled" json:"enabled"`
	Default string                       `yaml:"default" json:"default"`
	Clients map[string]*HTTPClientConfig `yaml:"clients" json:"clients"`
}

func (c *HTTPClientsConfig) applyDefaults() {
	if c.Clients == nil {
		c.Clients = map[string]*HTTPClientConfig{}
	}
	// Ensure at least one default client
	if c.Default == "" {
		c.Default = "default"
	}
	if _, ok := c.Clients[c.Default]; !ok {
		c.Clients[c.Default] = &HTTPClientConfig{}
	}
	for name, cfg := range c.Clients {
		if cfg.Timeout <= 0 {
			cfg.Timeout = 10 * time.Second
		}
		if cfg.MaxIdleConns == 0 {
			cfg.MaxIdleConns = 200
		}
		if cfg.MaxIdleConnsPerHost == 0 {
			cfg.MaxIdleConnsPerHost = 100
		}
		if cfg.IdleConnTimeout == 0 {
			cfg.IdleConnTimeout = 90 * time.Second
		}
		if cfg.DefaultHeaders == nil {
			cfg.DefaultHeaders = map[string]string{}
		}
		if cfg.Retry != nil {
			if cfg.Retry.MaxAttempts <= 0 {
				cfg.Retry.MaxAttempts = 3
			}
			if cfg.Retry.InitialBackoff <= 0 {
				cfg.Retry.InitialBackoff = 100 * time.Millisecond
			}
			if cfg.Retry.MaxBackoff <= 0 {
				cfg.Retry.MaxBackoff = 2 * time.Second
			}
			if cfg.Retry.BackoffMultiplier <= 1 {
				cfg.Retry.BackoffMultiplier = 2
			}
		}
		// Normalize base url (remove trailing slash)
		if cfg.BaseURL != "" && cfg.BaseURL[len(cfg.BaseURL)-1] == '/' {
			cfg.BaseURL = cfg.BaseURL[:len(cfg.BaseURL)-1]
		}
		// Guarantee default exists
		if name == c.Default && cfg.BaseURL == "" {
			// leave empty (relative usage) or set your internal base here
		}
	}
}
