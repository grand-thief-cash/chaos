package config

import (
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
)

var (
	bizConfig *BizConfig
)

func GetBizConfig() *BizConfig {
	return bizConfig
}

type SchedulerConfig struct {
	PollInterval time.Duration `yaml:"poll_interval"`
}

type ExecutorConfig struct {
	WorkerPoolSize int           `yaml:"worker_pool_size"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
}

type CallbackScannerConfig struct {
	Interval   time.Duration `yaml:"interval"`
	BatchLimit int           `yaml:"batch_limit"`
}

type CleanupConfig struct {
	Enabled    bool          `yaml:"enabled"`
	Interval   time.Duration `yaml:"interval"`     // background cleanup interval
	MaxAge     time.Duration `yaml:"max_age"`      // auto delete runs older than MaxAge
	MaxPerTask int           `yaml:"max_per_task"` // auto keep recent N per task
	DryRun     bool          `yaml:"dry_run"`      // log only
}

type BizConfig struct {
	//Server    ServerConfig    `yaml:"server"`
	//MySQL     MySQLConfig     `yaml:"mysql"`
	Scheduler       SchedulerConfig       `yaml:"scheduler"`
	Executor        ExecutorConfig        `yaml:"executor"`
	CallbackScanner CallbackScannerConfig `yaml:"callback_scanner"`
	Cleanup         CleanupConfig         `yaml:"cleanup"`
}

func init() {
	bizConfig = &BizConfig{}
	app := application.GetApp()
	app.SetBizConfig(bizConfig)
}
