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

type BizConfig struct {
	//Server    ServerConfig    `yaml:"server"`
	//MySQL     MySQLConfig     `yaml:"mysql"`
	Scheduler SchedulerConfig `yaml:"scheduler"`
	Executor  ExecutorConfig  `yaml:"executor"`
}

func init() {
	bizConfig = &BizConfig{}
	app := application.GetApp()
	app.SetBizConfig(bizConfig)
}
