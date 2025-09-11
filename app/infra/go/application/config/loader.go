// config/loader.go
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"gopkg.in/yaml.v3"
)

// Loader 配置加载器
type Loader struct {
	env        string
	configPath string
}

// NewLoader 创建配置加载器
func NewLoader(env string, configPath string) *Loader {
	if env == "" {
		env = consts.ENV_DEVELOPMENT
	}
	if configPath == "" {
		configPath = consts.DEFAULT_CONFIG_PATH
	}
	return &Loader{
		env:        env,
		configPath: configPath,
	}
}

// LoadConfig 加载配置文件
func (l *Loader) LoadConfig() (*AppConfig, error) {

	data, err := os.ReadFile(l.configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var config AppConfig
	ext := strings.ToLower(filepath.Ext(l.configPath))

	switch ext {
	case ".yaml", ".yml":
		if err := yaml.Unmarshal(data, &config); err != nil {
			return nil, fmt.Errorf("failed to parse YAML config: %w", err)
		}
	case ".json":
		if err := json.Unmarshal(data, &config); err != nil {
			return nil, fmt.Errorf("failed to parse JSON config: %w", err)
		}
	default:
		return nil, fmt.Errorf("unsupported config file format: %s", ext)
	}

	// 合并环境变量
	l.mergeEnvVars(&config)

	return &config, nil
}

// mergeEnvVars 合并环境变量到配置中
func (l *Loader) mergeEnvVars(config *AppConfig) {
	// 这里可以实现环境变量覆盖逻辑
	// 例如：GOINFRA_DATABASE_MYSQL_HOST 覆盖 config.Database.MySQL.Host

	//if val := os.Getenv(l.envPrefix + "SERVER_GIN_PORT"); val != "" && config.Server.Gin != nil {
	//	// 这里需要字符串转换为int，简化示例
	//	// config.Server.Gin.Port = stringToInt(val)
	//}

	// 可以继续添加更多环境变量覆盖逻辑
}

// fileExists 检查文件是否存在
func fileExists(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}
