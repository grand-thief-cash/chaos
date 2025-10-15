// config/loader.go
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"gopkg.in/yaml.v3"
)

// Loader 配置加载器
type Loader struct {
	env        string
	configPath string
	// bizConfig: 业务方传入的指针, 用于填充 biz_config 小节
	bizConfig any
}

// NewLoader 创建配置加载器
func NewLoader(env string, configPath string) *Loader {
	if env == "" {
		env = consts.ENV_DEVELOPMENT
	}
	if configPath == "" {
		configPath = consts.DEFAULT_CONFIG_PATH
	}
	return &Loader{env: env, configPath: configPath}
}

// SetBizConfig 注入业务方自定义配置结构指针 (例如: &MyBizConfig{}). 需要在 LoadConfig 之前调用。
// 传入的必须是一个指针, 这样 decoder 会直接填充该结构体。
func (l *Loader) SetBizConfig(b any) {
	if b == nil {
		return
	}
	if reflect.TypeOf(b).Kind() != reflect.Ptr {
		panic("SetBizConfig expects a pointer, e.g. &MyBizConfig{}")
	}
	l.bizConfig = b
}

// LoadConfig: 先整体解析 AppConfig, 再把 biz_config 子树二次反序列化到业务指针。
// 之前的方式(预先把指针放入 interface{}) 在 yaml.v3 中不会按期望覆盖指针内部字段, 会被替换成 map。
func (l *Loader) LoadConfig() (*AppConfig, error) {
	data, err := os.ReadFile(l.configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg AppConfig
	ext := strings.ToLower(filepath.Ext(l.configPath))
	switch ext {
	case ".yaml", ".yml":
		if err := yaml.Unmarshal(data, &cfg); err != nil {
			return nil, fmt.Errorf("failed to parse YAML config: %w", err)
		}
	case ".json":
		if err := json.Unmarshal(data, &cfg); err != nil {
			return nil, fmt.Errorf("failed to parse JSON config: %w", err)
		}
	default:
		return nil, fmt.Errorf("unsupported config file format: %s", ext)
	}

	// 如果业务方提供了指针, 且文件中存在 biz_config 数据, 做二次解码
	if l.bizConfig != nil && cfg.BizConfig != nil {
		if err := l.decodeBizSection(ext, cfg.BizConfig, l.bizConfig); err != nil {
			return nil, fmt.Errorf("decode biz_config failed: %w", err)
		}
		cfg.BizConfig = l.bizConfig // 用业务方真实指针替换接口里的 map
	} else if l.bizConfig != nil && cfg.BizConfig == nil {
		// 文件没有 biz_config, 但用户有默认值, 直接挂上
		cfg.BizConfig = l.bizConfig
	}

	l.mergeEnvVars(&cfg)
	return &cfg, nil
}

// decodeBizSection 将已解析到的 interface{} 子树再序列化 + 反序列化到业务指针 (支持保留默认值)。
func (l *Loader) decodeBizSection(ext string, raw any, target any) error {
	var (
		bytes []byte
		err   error
	)
	switch ext {
	case ".yaml", ".yml":
		bytes, err = yaml.Marshal(raw)
	case ".json":
		bytes, err = json.Marshal(raw)
	default:
		return fmt.Errorf("unsupported format: %s", ext)
	}
	if err != nil {
		return fmt.Errorf("re-marshal biz_config failed: %w", err)
	}
	switch ext {
	case ".yaml", ".yml":
		if err := yaml.Unmarshal(bytes, target); err != nil {
			return fmt.Errorf("unmarshal biz_config into target failed: %w", err)
		}
	case ".json":
		if err := json.Unmarshal(bytes, target); err != nil {
			return fmt.Errorf("unmarshal biz_config into target failed: %w", err)
		}
	}
	return nil
}

// mergeEnvVars 合并环境变量到配置中
func (l *Loader) mergeEnvVars(_ *AppConfig) {
	// TODO: 可选实现��境变量覆盖逻辑
}

// fileExists 检查文件是否存在
func fileExists(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}
