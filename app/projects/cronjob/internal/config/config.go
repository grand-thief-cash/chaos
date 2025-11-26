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

type ScannerConfig struct {
	Interval                    time.Duration `yaml:"interval"`
	BatchLimit                  int           `yaml:"batch_limit"`
	SyncRunStuckTimeoutSeconds  int           `yaml:"sync_run_stuck_timeout_seconds"` // RUNNING SYNC runs exceeding this age considered stuck; 0 disables
	ProgressCleanupGraceSeconds int           `yaml:"progress_cleanup_grace_seconds"` // grace after terminal end_time before progress cleared; 0 immediate
}

type CleanupConfig struct {
	Enabled    bool          `yaml:"enabled"`
	Interval   time.Duration `yaml:"interval"`     // background cleanup interval
	MaxAge     time.Duration `yaml:"max_age"`      // auto delete runs older than MaxAge
	MaxPerTask int           `yaml:"max_per_task"` // auto keep recent N per task
}

type CallbackEndpointsConfig struct {
	ProgressPath string `yaml:"progress_path"` // e.g. /runs/{run_id}/progress
	CallbackPath string `yaml:"callback_path"` // e.g. /runs/{run_id}/callback
}

type BizConfig struct {
	Scheduler         SchedulerConfig         `yaml:"scheduler"`
	Executor          ExecutorConfig          `yaml:"executor"`
	Scanner           ScannerConfig           `yaml:"scanner"`
	Cleanup           CleanupConfig           `yaml:"cleanup"`
	CallbackEndpoints CallbackEndpointsConfig `yaml:"callback_endpoints"`
}

func init() {
	bizConfig = &BizConfig{}
	app := application.GetApp()
	app.SetBizConfig(bizConfig)
}
