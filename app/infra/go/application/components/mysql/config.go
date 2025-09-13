// components/mysql/config.go
package mysql

import "time"

// MySQLConfig top-level mysql config supporting multiple named data sources.
type MySQLConfig struct {
	Enabled     bool                              `yaml:"enabled" json:"enabled"`
	DataSources map[string]*MySQLDataSourceConfig `yaml:"data_sources" json:"data_sources"`
}

// MySQLDataSourceConfig single datasource settings.
type MySQLDataSourceConfig struct {
	// Either supply full DSN or connection pieces.
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
}
