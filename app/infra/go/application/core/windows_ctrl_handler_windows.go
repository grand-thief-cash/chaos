//go:build windows

package core

import (
	"context"
	"log"
	"sync"
	"syscall"
	"time"
)

// Windows console control handler integration.
// Catches CTRL_C_EVENT, CTRL_BREAK_EVENT, console close, logoff, system shutdown and triggers cancel once.

var (
	ctrlOnce sync.Once
)

func InstallWindowsCtrlHandler(cancel context.CancelFunc, timeout time.Duration) {
	// Prepare callback referencing the provided cancel.
	handler := func(ctrlType uint32) uintptr {
		// https://learn.microsoft.com/en-us/windows/console/handlerroutine
		switch ctrlType {
		case 0, 1, 2, 5, 6: // CTRL_C_EVENT=0, CTRL_BREAK_EVENT=1, CTRL_CLOSE_EVENT=2, CTRL_LOGOFF_EVENT=5, CTRL_SHUTDOWN_EVENT=6
			ctrlOnce.Do(func() {
				log.Printf("Windows console control event %d received, initiating graceful shutdown...", ctrlType)
				cancel()
			})
			return 1 // handled
		default:
			return 0
		}
	}

	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	procSetConsoleCtrlHandler := kernel32.NewProc("SetConsoleCtrlHandler")

	cb := syscall.NewCallback(handler)
	// BOOL SetConsoleCtrlHandler(PHANDLER_ROUTINE HandlerRoutine, BOOL Add);
	ret, _, err := procSetConsoleCtrlHandler.Call(cb, 1)
	if ret == 0 {
		log.Printf("SetConsoleCtrlHandler registration failed: %v", err)
	} else {
		log.Printf("Windows console control handler installed")
	}
}
