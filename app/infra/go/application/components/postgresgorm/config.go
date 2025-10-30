package postgresgorm

import "time"

// Config top-level gorm postgres config supporting multiple named data sources and gorm specific options.
type Config struct {
	Enabled       bool                         `yaml:"enabled" json:"enabled"`
	DataSources   map[string]*DataSourceConfig `yaml:"data_sources" json:"data_sources"`
	LogLevel      string                       `yaml:"log_level" json:"log_level"`           // silent|error|warn|info|debug
	SlowThreshold time.Duration                `yaml:"slow_threshold" json:"slow_threshold"` // e.g. 200ms
}

// DataSourceConfig single datasource settings.
type DataSourceConfig struct {
	DSN string `yaml:"dsn" json:"dsn"`

	Host     string            `yaml:"host" json:"host"`
	Port     int               `yaml:"port" json:"port"`
	User     string            `yaml:"user" json:"user"`
	Password string            `yaml:"password" json:"password"`
	Database string            `yaml:"database" json:"database"`
	Params   map[string]string `yaml:"params" json:"params"`

	MaxOpenConns int           `yaml:"max_open_conns" json:"max_open_conns"`
	MaxIdleConns int           `yaml:"max_idle_conns" json:"max_idle_conns"`
	ConnMaxLife  time.Duration `yaml:"conn_max_life" json:"conn_max_life"`
	ConnMaxIdle  time.Duration `yaml:"conn_max_idle" json:"conn_max_idle"`
	PingOnStart  bool          `yaml:"ping_on_start" json:"ping_on_start"`

	SkipDefaultTransaction bool `yaml:"skip_default_tx" json:"skip_default_tx"`
	PrepareStmt            bool `yaml:"prepare_stmt" json:"prepare_stmt"`

	MigrateEnabled bool   `yaml:"migrate_enabled" json:"migrate_enabled"`
	MigrateDir     string `yaml:"migrate_dir" json:"migrate_dir"`

	// Optional: timescaleDB/TSDB extension handling.
	EnableTimescale bool   `yaml:"enable_timescale" json:"enable_timescale"` // if true attempt to create extension timescaledb
	TimescaleSchema string `yaml:"timescale_schema" json:"timescale_schema"` // optional schema for timescaledb
}
