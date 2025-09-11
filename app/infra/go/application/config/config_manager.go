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

func NewConfigManager(env string, configPath string) (*ConfigManager, error) {
	validator := NewValidator()
	loader := NewLoader(env, configPath)

	if err := validator.validateConfigFilePath(env, configPath); err != nil {
		return nil, err
	}

	return &ConfigManager{
		configLoader: loader,
		validator:    validator,
	}, nil
}
