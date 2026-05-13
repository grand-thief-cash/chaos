// file: app/infra/go/application/components/telemetry/config.go
package telemetry

import "time"

type ExporterType string

const (
	ExporterNone   ExporterType = "none"
	ExporterStdout ExporterType = "stdout"
	ExporterFile   ExporterType = "file"
	ExporterOTLP   ExporterType = "otlp"
)

type OTLPConfig struct {
	Endpoint string `yaml:"endpoint" json:"endpoint"`
	Insecure bool   `yaml:"insecure" json:"insecure"`
	Timeout  string `yaml:"timeout"  json:"timeout"`
}

type Config struct {
	Enabled      bool         `yaml:"enabled"       json:"enabled"`
	ServiceName  string       `yaml:"service_name"  json:"service_name"`
	Exporter     ExporterType `yaml:"exporter"      json:"exporter"` // none|stdout|file|otlp
	SampleRatio  float64      `yaml:"sample_ratio"  json:"sample_ratio"`
	OTLP         *OTLPConfig  `yaml:"otlp"          json:"otlp"`
	StdoutPretty bool         `yaml:"stdout_pretty" json:"stdout_pretty"` // for stdout exporter

	// File output settings (used when exporter: file)
	// Note: For backwards compatibility, if stdout_file is set with exporter: stdout,
	// the output will be redirected to the file. Use exporter: file for explicit file output.
	StdoutFile     string `yaml:"stdout_file"     json:"stdout_file"`         // file path for file exporter (or stdout with redirection)
	FileMaxSizeMB  int    `yaml:"file_max_size_mb"  json:"file_max_size_mb"`  // max size per file in MB (default 100)
	FileMaxAgeDays int    `yaml:"file_max_age_days" json:"file_max_age_days"` // max days to retain old files (default 7)
	FileMaxBackups int    `yaml:"file_max_backups"  json:"file_max_backups"`  // max number of old files (default 5)
}

func (c *Config) applyDefaults() {
	// ServiceName no longer auto-defaulted; must be provided upstream (e.g., from APPInfo.APPName)
	// sample_ratio: 0 means never sample, <0 or >1 is invalid
	if c.SampleRatio < 0 || c.SampleRatio > 1 {
		c.SampleRatio = 1.0
	}
	if c.Exporter == "" {
		// Prefer OTLP if endpoint is configured; otherwise default to no-op to avoid surprising log/file spam.
		if c.OTLP != nil && c.OTLP.Endpoint != "" {
			c.Exporter = ExporterOTLP
		} else if c.StdoutFile != "" {
			// If stdout_file is set but no exporter, use file exporter
			c.Exporter = ExporterFile
		} else {
			c.Exporter = ExporterNone
		}
	}
	if c.OTLP != nil && c.OTLP.Timeout == "" {
		c.OTLP.Timeout = "5s"
	}
	// Set default rotation values if file exporter is used
	if c.Exporter == ExporterFile || c.StdoutFile != "" {
		if c.FileMaxSizeMB <= 0 {
			c.FileMaxSizeMB = 100
		}
		if c.FileMaxAgeDays <= 0 {
			c.FileMaxAgeDays = 7
		}
		if c.FileMaxBackups <= 0 {
			c.FileMaxBackups = 5
		}
	}
}

func (c *Config) otlpTimeout() time.Duration {
	if c.OTLP == nil || c.OTLP.Timeout == "" {
		return 5 * time.Second
	}
	d, err := time.ParseDuration(c.OTLP.Timeout)
	if err != nil {
		return 5 * time.Second
	}
	return d
}
