package config

import "github.com/grand-thief-cash/chaos/app/infra/go/application"

var (
	bizConfig *BizConfig
)

func GetBizConfig() *BizConfig {
	return bizConfig
}

type BizConfig struct {
	TestConfig TestConfig `yaml:"test_config" json:"test_config"`
}

type TestConfig struct {
	Name string `yaml:"name" json:"name"`
	Age  int    `yaml:"age" json:"age"`
}

func init() {
	bizConfig = &BizConfig{}
	//application.GetApp().SetBizConfig(bizConfig)
	app := application.GetApp()
	app.SetBizConfig(bizConfig)
}
