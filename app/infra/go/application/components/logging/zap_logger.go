// components/logging/zap_logger.go
package logging

import (
	"context"
	"fmt"
	"github.com/google/uuid"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"gopkg.in/natefinch/lumberjack.v2"
	"os"
	"path/filepath"
	"strings"

	"github.com/grand-thief-cash/chaos/app/infra/infra_go/core"
)

const (
	TraceIDKey = "trace_id"
)

// Logger 日志记录器接口
type Logger interface {
	Debug(ctx context.Context, msg string, fields ...zap.Field)
	Info(ctx context.Context, msg string, fields ...zap.Field)
	Warn(ctx context.Context, msg string, fields ...zap.Field)
	Error(ctx context.Context, msg string, fields ...zap.Field)
	Fatal(ctx context.Context, msg string, fields ...zap.Field)
	With(fields ...zap.Field) Logger
	Sync() error
}

// ZapLoggerComponent Zap日志组件
type ZapLoggerComponent struct {
	*core.BaseComponent
	config    *LoggingConfig
	zapLogger *zap.Logger
	sugar     *zap.SugaredLogger
}

// NewZapLoggerComponent 创建新的Zap日志组件
func NewZapLoggerComponent(cfg *LoggingConfig) *ZapLoggerComponent {
	return &ZapLoggerComponent{
		BaseComponent: core.NewBaseComponent("zap_logger"),
		config:        cfg,
	}
}

// Start 启动日志组件
func (lc *ZapLoggerComponent) Start(ctx context.Context) error {
	if err := lc.BaseComponent.Start(ctx); err != nil {
		return err
	}

	// 创建编码器
	encoder := lc.buildEncoder()

	// 创建写入器
	writeSyncer, err := lc.buildWriteSyncer()
	if err != nil {
		return fmt.Errorf("failed to create write syncer: %w", err)
	}

	// 解析日志级别
	level := lc.parseLevel(lc.config.Level)

	// 创建core
	core := zapcore.NewCore(encoder, writeSyncer, level)

	// 创建logger
	lc.zapLogger = zap.New(core, zap.AddCaller(), zap.AddStacktrace(zapcore.ErrorLevel))
	lc.sugar = lc.zapLogger.Sugar()

	lc.zapLogger.Info("Zap logger component started",
		zap.String("level", lc.config.Level),
		zap.String("format", lc.config.Format),
		zap.String("output", lc.config.Output),
	)

	return nil
}

// Stop 停止日志组件
func (lc *ZapLoggerComponent) Stop(ctx context.Context) error {
	if lc.zapLogger != nil {
		lc.zapLogger.Info("Zap logger component stopping")
		_ = lc.zapLogger.Sync()
	}
	return lc.BaseComponent.Stop(ctx)
}

// HealthCheck 健康检查
func (lc *ZapLoggerComponent) HealthCheck() error {
	if err := lc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if lc.zapLogger == nil {
		return fmt.Errorf("zap logger is not initialized")
	}
	return nil
}

// buildEncoder 构建编码器
func (lc *ZapLoggerComponent) buildEncoder() zapcore.Encoder {
	encoderConfig := zapcore.EncoderConfig{
		TimeKey:        "timestamp",
		LevelKey:       "level",
		NameKey:        "logger",
		CallerKey:      "caller",
		FunctionKey:    zapcore.OmitKey,
		MessageKey:     "message",
		StacktraceKey:  "stacktrace",
		LineEnding:     zapcore.DefaultLineEnding,
		EncodeLevel:    zapcore.LowercaseLevelEncoder,
		EncodeTime:     zapcore.ISO8601TimeEncoder,
		EncodeDuration: zapcore.SecondsDurationEncoder,
		EncodeCaller:   zapcore.ShortCallerEncoder,
	}

	if lc.config.Format == "json" {
		return zapcore.NewJSONEncoder(encoderConfig)
	}
	return zapcore.NewConsoleEncoder(encoderConfig)
}

// buildWriteSyncer 构建写入器
func (lc *ZapLoggerComponent) buildWriteSyncer() (zapcore.WriteSyncer, error) {
	switch strings.ToLower(lc.config.Output) {
	case "stdout", "":
		return zapcore.AddSync(os.Stdout), nil
	case "stderr":
		return zapcore.AddSync(os.Stderr), nil
	case "file":
		return lc.buildFileWriteSyncer()
	default:
		// 如果不是标准关键字，当作文件路径处理
		return lc.buildCustomFileWriteSyncer(lc.config.Output)
	}
}

// buildFileWriteSyncer 构建文件写入器（使用配置的文件设置）
func (lc *ZapLoggerComponent) buildFileWriteSyncer() (zapcore.WriteSyncer, error) {
	if lc.config.FileConfig == nil {
		return nil, fmt.Errorf("file config is required when output is 'file'")
	}

	// 确保目录存在
	if err := os.MkdirAll(lc.config.FileConfig.Dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create log directory: %w", err)
	}

	logFile := filepath.Join(lc.config.FileConfig.Dir, lc.config.FileConfig.Filename+".log")

	// 如果启用了轮转，使用 lumberjack
	if lc.config.RotateConfig != nil && lc.config.RotateConfig.Enabled {
		lumber := &lumberjack.Logger{
			Filename:  logFile,
			MaxSize:   100,                                             // MB
			MaxAge:    int(lc.config.RotateConfig.MaxAge.Hours() / 24), // 转换为天数
			Compress:  true,
			LocalTime: true,
		}
		return zapcore.AddSync(lumber), nil
	}

	// 普通文件输出
	file, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}

	return zapcore.AddSync(file), nil
}

// buildCustomFileWriteSyncer 构建自定义文件写入器
func (lc *ZapLoggerComponent) buildCustomFileWriteSyncer(filePath string) (zapcore.WriteSyncer, error) {
	file, err := os.OpenFile(filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}
	return zapcore.AddSync(file), nil
}

// parseLevel 解析日志级别
func (lc *ZapLoggerComponent) parseLevel(level string) zapcore.Level {
	switch strings.ToUpper(level) {
	case "DEBUG":
		return zapcore.DebugLevel
	case "INFO":
		return zapcore.InfoLevel
	case "WARN", "WARNING":
		return zapcore.WarnLevel
	case "ERROR":
		return zapcore.ErrorLevel
	case "FATAL":
		return zapcore.FatalLevel
	default:
		return zapcore.InfoLevel
	}
}

// Debug 记录调试日志
func (lc *ZapLoggerComponent) Debug(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.DebugLevel, msg, fields...)
}

// Info 记录信息日志
func (lc *ZapLoggerComponent) Info(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.InfoLevel, msg, fields...)
}

// Warn 记录警告日志
func (lc *ZapLoggerComponent) Warn(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.WarnLevel, msg, fields...)
}

// Error 记录错误日志
func (lc *ZapLoggerComponent) Error(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.ErrorLevel, msg, fields...)
}

// Fatal 记录致命错误日志
func (lc *ZapLoggerComponent) Fatal(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.FatalLevel, msg, fields...)
	os.Exit(1)
}

// With 创建带有附加字段的新logger
func (lc *ZapLoggerComponent) With(fields ...zap.Field) Logger {
	return &ZapLoggerComponent{
		BaseComponent: lc.BaseComponent,
		config:        lc.config,
		zapLogger:     lc.zapLogger.With(fields...),
		sugar:         lc.sugar.With(fields),
	}
}

// Sync 同步日志
func (lc *ZapLoggerComponent) Sync() error {
	if lc.zapLogger != nil {
		return lc.zapLogger.Sync()
	}
	return nil
}

// logWithContext 带上下文的日志记录
func (lc *ZapLoggerComponent) logWithContext(ctx context.Context, level zapcore.Level, msg string, fields ...zap.Field) {
	if lc.zapLogger == nil {
		return
	}

	// 从context中获取或生成trace_id
	traceID := lc.getOrGenerateTraceID(ctx)
	allFields := append([]zap.Field{zap.String(TraceIDKey, traceID)}, fields...)

	switch level {
	case zapcore.DebugLevel:
		lc.zapLogger.Debug(msg, allFields...)
	case zapcore.InfoLevel:
		lc.zapLogger.Info(msg, allFields...)
	case zapcore.WarnLevel:
		lc.zapLogger.Warn(msg, allFields...)
	case zapcore.ErrorLevel:
		lc.zapLogger.Error(msg, allFields...)
	case zapcore.FatalLevel:
		lc.zapLogger.Fatal(msg, allFields...)
	}
}

// getOrGenerateTraceID 从context中获取或生成trace_id
func (lc *ZapLoggerComponent) getOrGenerateTraceID(ctx context.Context) string {
	if ctx == nil {
		return lc.generateTraceID()
	}

	// 尝试从context中获取trace_id
	if traceID := ctx.Value(TraceIDKey); traceID != nil {
		if id, ok := traceID.(string); ok && id != "" {
			return id
		}
	}

	// 尝试从context中获取其他可能的trace key
	traceKeys := []string{"traceId", "trace-id", "x-trace-id", "request-id"}
	for _, key := range traceKeys {
		if traceID := ctx.Value(key); traceID != nil {
			if id, ok := traceID.(string); ok && id != "" {
				return id
			}
		}
	}

	// 如果context中没有找到trace_id，生成一个新的
	return lc.generateTraceID()
}

// generateTraceID 生成新的trace_id
func (lc *ZapLoggerComponent) generateTraceID() string {
	return uuid.New().String()
}

// GetLogger 获取Logger接口
func (lc *ZapLoggerComponent) GetLogger() Logger {
	return lc
}

// GetZapLogger 获取原始的zap.Logger
func (lc *ZapLoggerComponent) GetZapLogger() *zap.Logger {
	return lc.zapLogger
}

// GetSugar 获取zap.SugaredLogger
func (lc *ZapLoggerComponent) GetSugar() *zap.SugaredLogger {
	return lc.sugar
}
