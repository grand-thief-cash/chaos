// file: app/infra/go/application/components/telemetry/config.go
package telemetry

import "time"

type ExporterType string

const (
	ExporterStdout ExporterType = "stdout"
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
	Exporter     ExporterType `yaml:"exporter"      json:"exporter"` // stdout|otlp
	SampleRatio  float64      `yaml:"sample_ratio"  json:"sample_ratio"`
	OTLP         *OTLPConfig  `yaml:"otlp"          json:"otlp"`
	StdoutPretty bool         `yaml:"stdout_pretty" json:"stdout_pretty"` // for stdout exporter
	StdoutFile   string       `yaml:"stdout_file"   json:"stdout_file"`   // if set, write telemetry output here
}

func (c *Config) applyDefaults() {
	// ServiceName no longer auto-defaulted; must be provided upstream (e.g., from APPInfo.APPName)
	if c.SampleRatio <= 0 || c.SampleRatio > 1 {
		c.SampleRatio = 1.0
	}
	if c.Exporter == "" {
		c.Exporter = ExporterStdout
	}
	if c.OTLP != nil && c.OTLP.Timeout == "" {
		c.OTLP.Timeout = "5s"
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
