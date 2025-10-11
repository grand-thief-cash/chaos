// components/logging/logger_component.go
package logging

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"gopkg.in/natefinch/lumberjack.v2"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

const (
	// 根据实际包装层数调整
	callerSkip = 3
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

// LoggerComponent Zap日志组件
type LoggerComponent struct {
	*core.BaseComponent
	config    *LoggingConfig
	zapLogger *zap.Logger
}

// NewLoggerComponent 创建新的Zap日志组件
func NewLoggerComponent(cfg *LoggingConfig) *LoggerComponent {
	return &LoggerComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_LOGGING),
		config:        cfg,
	}
}

// Start 启动日志组件
func (lc *LoggerComponent) Start(ctx context.Context) error {
	if err := lc.BaseComponent.Start(ctx); err != nil {
		return err
	}

	encoder := lc.buildEncoder()

	writeSyncer, err := lc.buildWriteSyncer()
	if err != nil {
		return fmt.Errorf("failed to create write syncer: %w", err)
	}

	level := lc.parseLevel(lc.config.Level)

	lc.zapLogger = zap.New(
		zapcore.NewCore(encoder, writeSyncer, level),
		zap.AddCaller(),
		zap.AddCallerSkip(callerSkip),
		zap.AddStacktrace(zapcore.ErrorLevel),
	)

	lc.zapLogger.Info("Zap logger component started",
		zap.String("level", lc.config.Level),
		zap.String("format", lc.config.Format),
		zap.String("output", lc.config.Output),
	)

	SetGlobalLogger(lc)
	return nil
}

// Stop 停止日志组件
func (lc *LoggerComponent) Stop(ctx context.Context) error {
	if lc.zapLogger != nil {
		Info(ctx, "logger component stopping")
		_ = lc.zapLogger.Sync()
	}
	return lc.BaseComponent.Stop(ctx)
}

// HealthCheck 健康检查
func (lc *LoggerComponent) HealthCheck() error {
	if err := lc.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	if lc.zapLogger == nil {
		return fmt.Errorf("zap logger is not initialized")
	}
	return nil
}

// buildEncoder 构建编码器
func (lc *LoggerComponent) buildEncoder() zapcore.Encoder {
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
func (lc *LoggerComponent) buildWriteSyncer() (zapcore.WriteSyncer, error) {
	switch strings.ToLower(lc.config.Output) {
	case "stdout", "":
		return zapcore.AddSync(os.Stdout), nil
	case "stderr":
		return zapcore.AddSync(os.Stderr), nil
	case "file":
		return lc.buildFileWriteSyncer()
	default:
		return lc.buildCustomFileWriteSyncer(lc.config.Output)
	}
}

// buildFileWriteSyncer 构建文件写入器（使用配置的文件设置）
func (lc *LoggerComponent) buildFileWriteSyncer() (zapcore.WriteSyncer, error) {
	if lc.config.FileConfig == nil {
		return nil, fmt.Errorf("file config is required when output is 'file'")
	}

	if err := os.MkdirAll(lc.config.FileConfig.Dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create log directory: %w", err)
	}

	baseName := lc.config.FileConfig.Filename
	logFile := filepath.Join(lc.config.FileConfig.Dir, baseName+".log")

	// Interval rotation (covers daily if interval = 24h)
	if rc := lc.config.RotateConfig; rc != nil && rc.Enabled && rc.RotateInterval > 0 {
		w, err := newIntervalRotatingWriter(lc.config.FileConfig.Dir, baseName, rc)
		if err != nil {
			return nil, err
		}
		return zapcore.AddSync(w), nil
	}

	// Size/age rotation fallback (lumberjack) if enabled but no interval
	if rc := lc.config.RotateConfig; rc != nil && rc.Enabled {
		lumber := &lumberjack.Logger{
			Filename:  logFile,
			MaxSize:   100,
			MaxAge:    int(rc.MaxAge.Hours() / 24),
			Compress:  true,
			LocalTime: true,
		}
		return zapcore.AddSync(lumber), nil
	}

	file, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}

	return zapcore.AddSync(file), nil
}

// buildCustomFileWriteSyncer 构建自定义文件写入器（路径可能包含目录）
func (lc *LoggerComponent) buildCustomFileWriteSyncer(filePath string) (zapcore.WriteSyncer, error) {
	dir := filepath.Dir(filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create custom log directory: %w", err)
	}
	file, err := os.OpenFile(filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}
	return zapcore.AddSync(file), nil
}

// parseLevel 解析日志级别
func (lc *LoggerComponent) parseLevel(level string) zapcore.Level {
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
func (lc *LoggerComponent) Debug(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.DebugLevel, msg, fields...)
}

// Info 记录信息日志
func (lc *LoggerComponent) Info(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.InfoLevel, msg, fields...)
}

// Warn 记录警告日志
func (lc *LoggerComponent) Warn(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.WarnLevel, msg, fields...)
}

// Error 记录错误日志
func (lc *LoggerComponent) Error(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.ErrorLevel, msg, fields...)
}

// Fatal 记录致命错误日志（依赖 zap 内部的 os.Exit）
func (lc *LoggerComponent) Fatal(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.FatalLevel, msg, fields...)
}

// With 创建带有附加字段的新logger
func (lc *LoggerComponent) With(fields ...zap.Field) Logger {
	return &LoggerComponent{
		BaseComponent: lc.BaseComponent,
		config:        lc.config,
		zapLogger:     lc.zapLogger.With(fields...),
	}
}

// Sync 同步日志
func (lc *LoggerComponent) Sync() error {
	if lc.zapLogger != nil {
		return lc.zapLogger.Sync()
	}
	return nil
}

// logWithContext 带上下文的日志记录，注入 OTel trace/span 信息（仅当存在有效 span）
func (lc *LoggerComponent) logWithContext(ctx context.Context, level zapcore.Level, msg string, fields ...zap.Field) {
	if lc.zapLogger == nil {
		return
	}

	if ctx != nil {
		sc := trace.SpanContextFromContext(ctx)
		if sc.IsValid() && sc.TraceID().IsValid() {
			if !hasField(fields, consts.KEY_TraceID) {
				fields = append([]zap.Field{zap.String(consts.KEY_TraceID, sc.TraceID().String())}, fields...)
			}
			if !hasField(fields, "span_id") {
				fields = append([]zap.Field{zap.String("span_id", sc.SpanID().String())}, fields...)
			}
			if !hasField(fields, "trace_flags") {
				fields = append([]zap.Field{zap.String("trace_flags", sc.TraceFlags().String())}, fields...)
			}
		}
	}

	switch level {
	case zapcore.DebugLevel:
		lc.zapLogger.Debug(msg, fields...)
	case zapcore.InfoLevel:
		lc.zapLogger.Info(msg, fields...)
	case zapcore.WarnLevel:
		lc.zapLogger.Warn(msg, fields...)
	case zapcore.ErrorLevel:
		lc.zapLogger.Error(msg, fields...)
	case zapcore.FatalLevel:
		lc.zapLogger.Fatal(msg, fields...)
	}
}

// hasField checks if given key exists among provided zap fields.
func hasField(fields []zap.Field, key string) bool {
	for _, f := range fields {
		if f.Key == key {
			return true
		}
	}
	return false
}

// GetLogger 获取Logger接口
func (lc *LoggerComponent) GetLogger() Logger { return lc }

// GetZapLogger 获取原始的zap.Logger
func (lc *LoggerComponent) GetZapLogger() *zap.Logger { return lc.zapLogger }
