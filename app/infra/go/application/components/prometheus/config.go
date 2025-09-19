package prometheus

// Config for Prometheus metrics exporter.
type Config struct {
	Enabled          bool   `yaml:"enabled" json:"enabled"`
	Address          string `yaml:"address" json:"address"` // e.g. ":9090"
	Path             string `yaml:"path" json:"path"`       // default /metrics
	Namespace        string `yaml:"namespace" json:"namespace"`
	Subsystem        string `yaml:"subsystem" json:"subsystem"`
	CollectGoMetrics bool   `yaml:"collect_go_metrics" json:"collect_go_metrics"` // default true
	CollectProcess   bool   `yaml:"collect_process" json:"collect_process"`       // default true
}
