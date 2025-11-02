package logging

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

// intervalRotatingWriter rotates log file based on configured interval (RotateInterval).
// Filenames follow pattern: <base>.log.YYYYMMDD (if interval >= 24h) else <base>.log.YYYYMMDDHHmmss
// This keeps the previously requested daily style while supporting arbitrary intervals.
type intervalRotatingWriter struct {
	mu        sync.Mutex
	dir       string
	baseName  string
	rotateCfg *RotateConfig

	currentFile *os.File
	currentTag  string    // date or timestamp tag used in filename
	openedAt    time.Time // time when current file opened
}

var (
	dateFileRegex     = regexp.MustCompile(`^.+\.log\.[0-9]{8}$`)
	dateTimeFileRegex = regexp.MustCompile(`^.+\.log\.[0-9]{14}$`)
)

func newIntervalRotatingWriter(dir, baseName string, rc *RotateConfig) (*intervalRotatingWriter, error) {
	if rc == nil || rc.RotateInterval <= 0 {
		return nil, fmt.Errorf("invalid rotate interval: %v", rc)
	}
	w := &intervalRotatingWriter{dir: dir, baseName: baseName, rotateCfg: rc}
	if err := w.rotateIfNeededLocked(time.Now()); err != nil {
		return nil, err
	}
	return w, nil
}

func (w *intervalRotatingWriter) filenameTag(t time.Time) string {
	if w.rotateCfg.RotateInterval >= 24*time.Hour { // daily style
		return t.Format("20060102")
	}
	return t.Format("20060102150405")
}

func (w *intervalRotatingWriter) filePathFor(tag string) string {
	return filepath.Join(w.dir, fmt.Sprintf("%s.log.%s", w.baseName, tag))
}

func (w *intervalRotatingWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if err := w.rotateIfNeededLocked(time.Now()); err != nil {
		return 0, err
	}
	return w.currentFile.Write(p)
}

func (w *intervalRotatingWriter) Sync() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.currentFile != nil {
		return w.currentFile.Sync()
	}
	return nil
}

func (w *intervalRotatingWriter) rotateIfNeededLocked(now time.Time) error {
	if w.currentFile != nil {
		elapsed := now.Sub(w.openedAt)
		if elapsed < w.rotateCfg.RotateInterval {
			return nil // still within interval
		}
		_ = w.currentFile.Sync()
		_ = w.currentFile.Close()
	}
	// open new file
	tag := w.filenameTag(now)
	path := w.filePathFor(tag)
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return fmt.Errorf("open rotated log file: %w", err)
	}
	w.currentFile = f
	w.currentTag = tag
	w.openedAt = now

	// cleanup
	if w.rotateCfg.CleanupEnabled && w.rotateCfg.MaxAge > 0 {
		w.cleanupOldLocked(now)
	}
	return nil
}

func (w *intervalRotatingWriter) cleanupOldLocked(now time.Time) {
	entries, err := os.ReadDir(w.dir)
	if err != nil {
		return
	}
	cutoff := now.Add(-w.rotateCfg.MaxAge)
	prefix := w.baseName + ".log."
	for _, e := range entries {
		name := e.Name()
		if !strings.HasPrefix(name, prefix) {
			continue
		}
		if !(dateFileRegex.MatchString(name) || dateTimeFileRegex.MatchString(name)) {
			continue
		}
		stamp := strings.TrimPrefix(name, prefix)
		layout := "20060102"
		if len(stamp) == 14 { // with time
			layout = "20060102150405"
		}
		parsed, err := time.Parse(layout, stamp)
		if err != nil {
			continue
		}
		if parsed.Before(cutoff) {
			_ = os.Remove(filepath.Join(w.dir, name))
		}
	}
}
