//go:build !windows

package core

import (
	"context"
	"time"
)

// InstallWindowsCtrlHandler is a no-op on non-Windows platforms.
// It exists only so code that unconditionally references the symbol
// (guarding at runtime with runtime.GOOS checks) still compiles when
// targeting Linux / macOS / other OSes.
func InstallWindowsCtrlHandler(cancel context.CancelFunc, timeout time.Duration) {
	// no-op
}
