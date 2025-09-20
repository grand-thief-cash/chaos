// components/logging/logger_component.go
package logging

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/google/uuid"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"gopkg.in/natefinch/lumberjack.v2"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

const (
	// 根据实际包装层数调整:
	// 典型: 3 (全局函数 + 组件方法 + logWithContext)
	// 如果仍显示在 logging 包内, 改成 4 试试
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
	sugar     *zap.SugaredLogger
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

	// 添加 AddCallerSkip 以跳过包装层
	lc.zapLogger = zap.New(
		zapcore.NewCore(encoder, writeSyncer, level),
		zap.AddCaller(),
		zap.AddCallerSkip(callerSkip),
		zap.AddStacktrace(zapcore.ErrorLevel),
	)
	lc.sugar = lc.zapLogger.Sugar()

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
		// 如果不是标准关键字，当作文件路径处理
		return lc.buildCustomFileWriteSyncer(lc.config.Output)
	}
}

// buildFileWriteSyncer 构建文件写入器（使用配置的文件设置）
func (lc *LoggerComponent) buildFileWriteSyncer() (zapcore.WriteSyncer, error) {
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
func (lc *LoggerComponent) buildCustomFileWriteSyncer(filePath string) (zapcore.WriteSyncer, error) {
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

// Fatal 记录致命错误日志
func (lc *LoggerComponent) Fatal(ctx context.Context, msg string, fields ...zap.Field) {
	lc.logWithContext(ctx, zapcore.FatalLevel, msg, fields...)
	os.Exit(1)
}

// With 创建带有附加字段的新logger
func (lc *LoggerComponent) With(fields ...zap.Field) Logger {
	return &LoggerComponent{
		BaseComponent: lc.BaseComponent,
		config:        lc.config,
		zapLogger:     lc.zapLogger.With(fields...),
		sugar:         lc.sugar.With(fields),
	}
}

// Sync 同步日志
func (lc *LoggerComponent) Sync() error {
	if lc.zapLogger != nil {
		return lc.zapLogger.Sync()
	}
	return nil
}

// logWithContext 带上下文的日志记录
// 新增辅助函数（可放在文件任意非方法位置）
func hasTraceField(fields []zap.Field) bool {
	for _, f := range fields {
		switch f.Key {
		case "trace_id", "trace-id":
			return true
		}
	}
	return false
}

// 修改 logWithContext
func (lc *LoggerComponent) logWithContext(ctx context.Context, level zapcore.Level, msg string, fields ...zap.Field) {
	if lc.zapLogger == nil {
		return
	}
	traceID := lc.extractTraceID(ctx)
	if traceID != "" && !hasTraceField(fields) {
		fields = append([]zap.Field{zap.String(consts.KEY_TraceID, traceID)}, fields...)
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

// getOrGenerateTraceID 从context中获取或生成trace_id
// getOrGenerateTraceID 优化：优先 OTel span trace id
func (lc *LoggerComponent) getOrGenerateTraceID(ctx context.Context) string {
	if ctx == nil {
		return lc.generateTraceID()
	}

	// 1. OpenTelemetry SpanContext
	if sc := trace.SpanContextFromContext(ctx); sc.IsValid() && sc.TraceID().IsValid() {
		return sc.TraceID().String()
	}

	// 2. 兼容旧 key（保持回退能力）
	if v := ctx.Value(consts.KEY_TraceID); v != nil {
		if id, ok := v.(string); ok && id != "" {
			return id
		}
	}

	// 3. 兼容其他可能 keys
	keys := []string{"traceId", "trace-id", "x-trace-id", "request-id", "traceID"}
	for _, k := range keys {
		if v := ctx.Value(k); v != nil {
			if id, ok := v.(string); ok && id != "" {
				return id
			}
		}
	}

	// 4. 兜底
	return lc.generateTraceID()
}

// generateTraceID 生成新的trace_id
func (lc *LoggerComponent) generateTraceID() string {
	return uuid.New().String()
}

// GetLogger 获取Logger接口
func (lc *LoggerComponent) GetLogger() Logger {
	return lc
}

// GetZapLogger 获取原始的zap.Logger
func (lc *LoggerComponent) GetZapLogger() *zap.Logger {
	return lc.zapLogger
}

// GetSugar 获取zap.SugaredLogger
func (lc *LoggerComponent) GetSugar() *zap.SugaredLogger {
	return lc.sugar
}

// extractTraceID: only use existing OTel trace id; do not synthesize a new distributed id.
// (Optional) If you still want a local fallback, add a generated UUID, but mark it clearly.
func (lc *LoggerComponent) extractTraceID(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if sc := trace.SpanContextFromContext(ctx); sc.IsValid() && sc.TraceID().IsValid() {
		return sc.TraceID().String()
	}
	return ""
}
