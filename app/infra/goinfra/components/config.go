package components

import (
	"context"
	"os"
	"strconv"
	"strings"
	"sync"
)

// ConfigComponent 配置管理组件
type ConfigComponent struct {
	name       string
	config     map[string]interface{}
	configPath string
	mu         sync.RWMutex
}

// NewConfigComponent 创建配置组件
func NewConfigComponent(configPath string) *ConfigComponent {
	return &ConfigComponent{
		name:       "config",
		config:     make(map[string]interface{}),
		configPath: configPath,
	}
}

// Name 返回组件名称
func (c *ConfigComponent) Name() string {
	return c.name
}

// Dependencies 返回依赖的组件
func (c *ConfigComponent) Dependencies() []string {
	return []string{}
}

// Initialize 初始化配置组件
func (c *ConfigComponent) Initialize(ctx context.Context, container *Container) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// 加载默认配置
	c.loadDefaultConfig()

	// 从环境变量加载
	c.loadFromEnv()

	// 从配置文件加载
	if c.configPath != "" {
		c.loadFromFile(c.configPath)
	}

	return nil
}

// Start 启动配置组件
func (c *ConfigComponent) Start(ctx context.Context) error {
	return nil
}

// Stop 停止配置组件
func (c *ConfigComponent) Stop(ctx context.Context) error {
	return nil
}

// Configure 配置组件
func (c *ConfigComponent) Configure(config map[string]interface{}) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.mergeConfig(c.config, config)
	return nil
}

// GetConfig 获取配置
func (c *ConfigComponent) GetConfig() map[string]interface{} {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make(map[string]interface{})
	c.mergeConfig(result, c.config)
	return result
}

// Get 获取配置值
func (c *ConfigComponent) Get(key string) interface{} {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.getNestedValue(c.config, key)
}

// Set 设置配置值
func (c *ConfigComponent) Set(key string, value interface{}) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.setNestedValue(c.config, key, value)
}

// Has 检查配置是否存在
func (c *ConfigComponent) Has(key string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.getNestedValue(c.config, key) != nil
}

// loadDefaultConfig 加载默认配置
func (c *ConfigComponent) loadDefaultConfig() {
	c.config = map[string]interface{}{
		"app": map[string]interface{}{
			"name":    "chaos-app",
			"version": "1.0.0",
			"debug":   false,
		},
		"server": map[string]interface{}{
			"host": "0.0.0.0",
			"port": 8080,
		},
		"database": map[string]interface{}{
			"host":     "localhost",
			"port":     3306,
			"database": "chaos",
			"username": "root",
			"password": "",
		},
		"redis": map[string]interface{}{
			"host":     "localhost",
			"port":     6379,
			"db":       0,
			"password": "",
		},
		"logging": map[string]interface{}{
			"level":  "INFO",
			"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
			"file":   nil,
		},
	}
}

// loadFromEnv 从环境变量加载配置
func (c *ConfigComponent) loadFromEnv() {
	envMapping := map[string][]string{
		"CHAOS_APP_NAME":       {"app", "name"},
		"CHAOS_APP_DEBUG":      {"app", "debug"},
		"CHAOS_SERVER_HOST":    {"server", "host"},
		"CHAOS_SERVER_PORT":    {"server", "port"},
		"CHAOS_DB_HOST":        {"database", "host"},
		"CHAOS_DB_PORT":        {"database", "port"},
		"CHAOS_DB_NAME":        {"database", "database"},
		"CHAOS_DB_USER":        {"database", "username"},
		"CHAOS_DB_PASSWORD":    {"database", "password"},
		"CHAOS_REDIS_HOST":     {"redis", "host"},
		"CHAOS_REDIS_PORT":     {"redis", "port"},
		"CHAOS_REDIS_DB":       {"redis", "db"},
		"CHAOS_REDIS_PASSWORD": {"redis", "password"},
		"CHAOS_LOG_LEVEL":      {"logging", "level"},
		"CHAOS_LOG_FILE":       {"logging", "file"},
	}

	for envVar, configPath := range envMapping {
		if value := os.Getenv(envVar); value != "" {
			convertedValue := c.convertValue(value)
			c.setNestedValue(c.config, configPath, convertedValue)
		}
	}
}

// loadFromFile 从文件加载配置
func (c *ConfigComponent) loadFromFile(filePath string) {
	// 这里可以实现从JSON、YAML等文件加载配置
	// 为了简化，这里只是一个占位符
}

// getNestedValue 获取嵌套值
func (c *ConfigComponent) getNestedValue(config map[string]interface{}, key string) interface{} {
	keys := strings.Split(key, ".")
	current := config

	for _, k := range keys {
		if currentMap, ok := current.(map[string]interface{}); ok {
			if value, exists := currentMap[k]; exists {
				current = value
			} else {
				return nil
			}
		} else {
			return nil
		}
	}

	return current
}

// setNestedValue 设置嵌套值
func (c *ConfigComponent) setNestedValue(config map[string]interface{}, key string, value interface{}) {
	keys := strings.Split(key, ".")
	current := config

	for _, k := range keys[:len(keys)-1] {
		if _, ok := current[k]; !ok {
			current[k] = make(map[string]interface{})
		}
		if currentMap, ok := current[k].(map[string]interface{}); ok {
			current = currentMap
		} else {
			// 如果不是map，则创建新的map
			newMap := make(map[string]interface{})
			current[k] = newMap
			current = newMap
		}
	}

	current[keys[len(keys)-1]] = value
}

// mergeConfig 合并配置
func (c *ConfigComponent) mergeConfig(base, update map[string]interface{}) {
	for key, value := range update {
		if baseValue, exists := base[key]; exists {
			if baseMap, ok := baseValue.(map[string]interface{}); ok {
				if updateMap, ok := value.(map[string]interface{}); ok {
					c.mergeConfig(baseMap, updateMap)
					continue
				}
			}
		}
		base[key] = value
	}
}

// convertValue 转换配置值类型
func (c *ConfigComponent) convertValue(value string) interface{} {
	// 尝试转换为布尔值
	if strings.ToLower(value) == "true" || strings.ToLower(value) == "yes" || value == "1" {
		return true
	}
	if strings.ToLower(value) == "false" || strings.ToLower(value) == "no" || value == "0" {
		return false
	}

	// 尝试转换为数字
	if strings.Contains(value, ".") {
		if floatValue, err := strconv.ParseFloat(value, 64); err == nil {
			return floatValue
		}
	} else {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}

	// 返回字符串
	return value
}
