package config

type ConfigManager struct {
	configLoader *Loader
	validator    *Validator
	appConfig    *AppConfig
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
