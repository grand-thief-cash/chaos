// app/poc_go/main.go
package main

import (
	"context"
	"fmt"
	"log"

	"go.uber.org/zap"

	"github.com/grand-thief-cash/chaos/app/infra/infra_go"
	"github.com/grand-thief-cash/chaos/app/infra/infra_go/hooks"
)

func main() {
	// 创建应用实例
	app := infra_go.NewApp()

	// 加载配置
	if err := app.LoadConfig("config/config.yaml"); err != nil {
		log.Fatal("Failed to load config:", err)
	}

	// 添加自定义钩子使用日志组件
	err := app.AddHook("demo_logging", hooks.AfterStart, func(ctx context.Context) error {
		logger, err := app.GetLogger()
		if err != nil {
			return fmt.Errorf("failed to get logger: %w", err)
		}

		// 创建带trace_id的context
		ctx = context.WithValue(ctx, "trace_id", "req-12345")

		logger.Info(ctx, "Application started with custom logging",
			zap.String("version", "1.0.0"),
			zap.String("environment", "development"),
		)

		logger.Debug(ctx, "Debug message",
			zap.String("key", "value"),
			zap.Int("count", 10),
		)

		logger.Warn(ctx, "Warning message",
			zap.String("component", "demo"),
		)

		logger.Error(ctx, "Error message",
			zap.Error(fmt.Errorf("demo error")),
		)

		// 使用带字段的logger
		contextLogger := logger.With(
			zap.String("request_id", "12345"),
			zap.String("user_id", "user123"),
		)
		contextLogger.Info(ctx, "User action performed",
			zap.String("action", "login"),
		)

		return nil
	}, 50)

	if err != nil {
		log.Fatal("Failed to add hook:", err)
	}

	// 启动应用
	if err := app.Run(); err != nil {
		log.Fatal("Failed to run app:", err)
	}
}
