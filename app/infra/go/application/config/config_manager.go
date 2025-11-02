package config

type ConfigManager struct {
	configLoader *Loader
	validator    *Validator
	appConfig    *AppConfig
}

// SetBizConfig 在加载前设置业务配置指针 (必须是指针). 需要在 LoadConfig 之前调用。
func (cf *ConfigManager) SetBizConfig(b any) {
	if cf != nil && cf.configLoader != nil {
		cf.configLoader.SetBizConfig(b)
	}
}

// BizConfig 返回 interface{} 业务配置 (原始指针)
func (cf *ConfigManager) BizConfig() any {
	if cf == nil || cf.appConfig == nil {
		return nil
	}
	return cf.appConfig.BizConfig
}

func (cf *ConfigManager) GetConfig() *AppConfig {
	return cf.appConfig
}

func (cf *ConfigManager) LoadConfig() error {

	if err := cf.validator.validateConfigFilePath(cf.configLoader.env, cf.configLoader.configPath); err != nil {
		return err
	}

	config, err := cf.configLoader.LoadConfig()
	if err != nil {
		return err
	}

	if err = cf.validator.ValidateAppConfig(config); err != nil {
		return err
	}

	cf.appConfig = config
	return nil
}

func NewConfigManager(env string, configPath string) *ConfigManager {
	validator := NewValidator()
	loader := NewLoader(env, configPath)

	return &ConfigManager{
		configLoader: loader,
		validator:    validator,
	}
}

// NewConfigManagerWithBiz 便捷构造: 直接提供业务配置指针
func NewConfigManagerWithBiz(env, configPath string, biz any) *ConfigManager {
	cm := NewConfigManager(env, configPath)
	cm.SetBizConfig(biz)
	return cm
}
