package logging

import (
	"context"
	"fmt"
	"sync"

	"go.uber.org/zap"
)

// Thread-safe global logger holder with a no-op default.
var (
	mu           sync.RWMutex
	globalLogger Logger = &noopLogger{}
)

// noopLogger is a safe placeholder before real logger initialization.
type noopLogger struct{}

func (n *noopLogger) Debug(ctx context.Context, msg string, fields ...zap.Field) {}
func (n *noopLogger) Info(ctx context.Context, msg string, fields ...zap.Field)  {}
func (n *noopLogger) Warn(ctx context.Context, msg string, fields ...zap.Field)  {}
func (n *noopLogger) Error(ctx context.Context, msg string, fields ...zap.Field) {}
func (n *noopLogger) Fatal(ctx context.Context, msg string, fields ...zap.Field) {}
func (n *noopLogger) With(fields ...zap.Field) Logger                            { return n }
func (n *noopLogger) Sync() error                                                { return nil }

// SetGlobalLogger sets the global logger (overwrite allowed).
func SetGlobalLogger(l Logger) {
	if l == nil {
		return
	}
	mu.Lock()
	globalLogger = l
	mu.Unlock()
}

// L returns the current global logger.
func L() Logger {
	mu.RLock()
	l := globalLogger
	mu.RUnlock()
	return l
}

// Structured convenience helpers.
func Debug(ctx context.Context, msg string, fields ...zap.Field) { L().Debug(ctx, msg, fields...) }
func Info(ctx context.Context, msg string, fields ...zap.Field)  { L().Info(ctx, msg, fields...) }
func Warn(ctx context.Context, msg string, fields ...zap.Field)  { L().Warn(ctx, msg, fields...) }
func Error(ctx context.Context, msg string, fields ...zap.Field) { L().Error(ctx, msg, fields...) }
func Fatal(ctx context.Context, msg string, fields ...zap.Field) { L().Fatal(ctx, msg, fields...) }

// Formatted convenience helpers.
func Debugf(ctx context.Context, format string, args ...interface{}) {
	L().Debug(ctx, fmt.Sprintf(format, args...))
}
func Infof(ctx context.Context, format string, args ...interface{}) {
	L().Info(ctx, fmt.Sprintf(format, args...))
}
func Warnf(ctx context.Context, format string, args ...interface{}) {
	L().Warn(ctx, fmt.Sprintf(format, args...))
}
func Errorf(ctx context.Context, format string, args ...interface{}) {
	L().Error(ctx, fmt.Sprintf(format, args...))
}
func Fatalf(ctx context.Context, format string, args ...interface{}) {
	L().Fatal(ctx, fmt.Sprintf(format, args...))
}

// Optional: expose underlying *zap.Logger when available.
func UnderlyingZap() *zap.Logger {
	if zc, ok := L().(*ZapLoggerComponent); ok {
		return zc.GetZapLogger()
	}
	return nil
}
