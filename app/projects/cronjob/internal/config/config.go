package config

import (
	"io/ioutil"
	"strconv"
	"time"

	"gopkg.in/yaml.v3"
)

type ServerConfig struct {
	Host            string        `yaml:"host"`
	Port            int           `yaml:"port"`
	GracefulTimeout time.Duration `yaml:"graceful_timeout"`
}

func (s ServerConfig) Address() string { return s.Host + ":" + strconv.FormatInt(int64(s.Port), 10) }

type MySQLConfig struct {
	DSN            string `yaml:"dsn"`
	MaxOpenConns   int    `yaml:"max_open_conns"`
	MaxIdleConns   int    `yaml:"max_idle_conns"`
	ConnMaxLifeSec int    `yaml:"conn_max_lifetime"`
}

type SchedulerConfig struct {
	PollInterval  time.Duration `yaml:"poll_interval"`
	AheadSeconds  int           `yaml:"ahead_seconds"`
	BatchLimit    int           `yaml:"batch_limit"`
	EnableSeconds bool          `yaml:"enable_seconds_field"`
}

type ExecutorSection struct {
	WorkerPoolSize int           `yaml:"worker_pool_size"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
}

type Config struct {
	Server    ServerConfig    `yaml:"server"`
	MySQL     MySQLConfig     `yaml:"mysql"`
	Scheduler SchedulerConfig `yaml:"scheduler"`
	Executor  ExecutorSection `yaml:"executor"`
}

func Load(path string) (*Config, error) {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return defaultConfig(), nil // fallback to defaults if file missing
	}
	cfg := defaultConfig()
	if err := yaml.Unmarshal(b, cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func defaultConfig() *Config {
	return &Config{
		Server:    ServerConfig{Host: "0.0.0.0", Port: 8080, GracefulTimeout: 10 * time.Second},
		MySQL:     MySQLConfig{DSN: "root:root@tcp(127.0.0.1:3306)/cronjob?parseTime=true&loc=Local", MaxOpenConns: 50, MaxIdleConns: 10, ConnMaxLifeSec: 300},
		Scheduler: SchedulerConfig{PollInterval: time.Second, AheadSeconds: 30, BatchLimit: 200, EnableSeconds: true},
		Executor:  ExecutorSection{WorkerPoolSize: 8, RequestTimeout: 15 * time.Second},
	}
}
