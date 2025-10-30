package postgresgorm

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	gormpg "gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// PostgresGormComponent manages multiple gorm DB connections for postgres (optionally timescaleDB).
type PostgresGormComponent struct {
	*core.BaseComponent
	cfg   *Config
	dbs   map[string]*gorm.DB
	mutex sync.RWMutex
	log   logger.Interface
}

func NewPostgresGormComponent(cfg *Config) *PostgresGormComponent {
	c := &PostgresGormComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_POSTGRES_GORM, consts.COMPONENT_LOGGING),
		cfg:           cfg,
		dbs:           make(map[string]*gorm.DB),
	}
	c.log = newGormLogger(cfg)
	return c
}

func (c *PostgresGormComponent) Start(ctx context.Context) error {
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if c.cfg == nil || !c.cfg.Enabled {
		return fmt.Errorf("postgres_gorm component disabled or nil config")
	}
	if len(c.cfg.DataSources) == 0 {
		return fmt.Errorf("postgres_gorm no data_sources configured")
	}
	for name, ds := range c.cfg.DataSources {
		if ds == nil {
			return fmt.Errorf("datasource %s config is nil", name)
		}
		dsn, err := buildDSN(ds)
		if err != nil {
			return fmt.Errorf("build dsn for %s failed: %w", name, err)
		}
		gormDB, err := gorm.Open(gormpg.Open(dsn), &gorm.Config{
			Logger:                 c.log,
			SkipDefaultTransaction: ds.SkipDefaultTransaction,
			PrepareStmt:            ds.PrepareStmt,
		})
		if err != nil {
			return fmt.Errorf("open gorm postgres db %s failed: %w", name, err)
		}
		sqlDB, err := gormDB.DB()
		if err != nil {
			return fmt.Errorf("get underlying sql.DB for %s failed: %w", name, err)
		}
		if ds.MaxOpenConns > 0 {
			sqlDB.SetMaxOpenConns(ds.MaxOpenConns)
		} else {
			sqlDB.SetMaxOpenConns(50)
		}
		if ds.MaxIdleConns > 0 {
			sqlDB.SetMaxIdleConns(ds.MaxIdleConns)
		} else {
			sqlDB.SetMaxIdleConns(10)
		}
		if ds.ConnMaxLife > 0 {
			sqlDB.SetConnMaxLifetime(ds.ConnMaxLife)
		} else {
			sqlDB.SetConnMaxLifetime(60 * time.Minute)
		}
		if ds.ConnMaxIdle > 0 {
			sqlDB.SetConnMaxIdleTime(ds.ConnMaxIdle)
		}

		if ds.PingOnStart {
			pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
			if err := sqlDB.PingContext(pingCtx); err != nil {
				cancel()
				_ = sqlDB.Close()
				return fmt.Errorf("ping postgres db %s failed: %w", name, err)
			}
			cancel()
		}

		// Optional migrations
		if ds.MigrateEnabled {
			if strings.TrimSpace(ds.MigrateDir) == "" {
				_ = sqlDB.Close()
				return fmt.Errorf("postgres_gorm datasource %s migrate_enabled=true but migrate_dir empty", name)
			}
			migStart := time.Now()
			logging.Infof(ctx, "[postgres_gorm] datasource %s running migrations dir=%s", name, ds.MigrateDir)
			if err := runGormMigrations(ctx, sqlDB, ds.MigrateDir); err != nil {
				_ = sqlDB.Close()
				return fmt.Errorf("postgres_gorm datasource %s migrations failed: %w", name, err)
			}
			logging.Infof(ctx, "[postgres_gorm] datasource %s migrations completed dur=%s", name, time.Since(migStart))
		}

		// TimescaleDB extension handling
		if ds.EnableTimescale {
			if err := ensureTimescaleExtension(ctx, sqlDB, ds.TimescaleSchema); err != nil {
				_ = sqlDB.Close()
				return fmt.Errorf("enable timescale for %s failed: %w", name, err)
			}
			logging.Infof(ctx, "[postgres_gorm] timescale extension ensured for datasource %s", name)
		}

		c.mutex.Lock()
		c.dbs[name] = gormDB
		c.mutex.Unlock()
		logging.Infof(ctx, "[postgres_gorm] datasource %s initialized", name)
	}
	logging.Infof(ctx, "[postgres_gorm] started. data sources=%v", c.listNames())
	return nil
}

func (c *PostgresGormComponent) Stop(ctx context.Context) error {
	defer func() { _ = c.BaseComponent.Stop(ctx) }()
	c.mutex.Lock()
	defer c.mutex.Unlock()
	for name, gdb := range c.dbs {
		if gdb != nil {
			if sqlDB, err := gdb.DB(); err == nil {
				_ = sqlDB.Close()
			}
			logging.Infof(ctx, "[postgres_gorm] datasource %s closed", name)
		}
	}
	return nil
}

func (c *PostgresGormComponent) HealthCheck() error {
	if err := c.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	for name, gdb := range c.dbs {
		if gdb == nil {
			return fmt.Errorf("datasource %s not initialized", name)
		}
		sqlDB, err := gdb.DB()
		if err != nil {
			return fmt.Errorf("datasource %s get sql.DB failed: %w", name, err)
		}
		if err := sqlDB.Ping(); err != nil {
			return fmt.Errorf("datasource %s ping failed: %w", name, err)
		}
	}
	return nil
}

func (c *PostgresGormComponent) GetDB(name string) (*gorm.DB, error) {
	c.mutex.RLock()
	db, ok := c.dbs[name]
	c.mutex.RUnlock()
	if !ok {
		return nil, fmt.Errorf("postgres_gorm datasource %s not found", name)
	}
	return db, nil
}

func (c *PostgresGormComponent) GetSQLDB(name string) (*sql.DB, error) { // raw *sql.DB accessor
	g, err := c.GetDB(name)
	if err != nil {
		return nil, err
	}
	sqlDB, e := g.DB()
	if e != nil {
		return nil, fmt.Errorf("get sql.DB for %s: %w", name, e)
	}
	return sqlDB, nil
}

// EnsureHypertable ensures a TimescaleDB hypertable exists for given table.
// chunkInterval example: "1 day" or "6 hours". Empty chunkInterval lets Timescale decide.
func (c *PostgresGormComponent) EnsureHypertable(ctx context.Context, dsName, table, timeColumn, chunkInterval string) error {
	ds, err := c.GetSQLDB(dsName)
	if err != nil {
		return err
	}
	if table == "" || timeColumn == "" {
		return fmt.Errorf("table and timeColumn required")
	}
	var stmt string
	if strings.TrimSpace(chunkInterval) != "" {
		// Using INTERVAL literal.
		stmt = fmt.Sprintf("SELECT create_hypertable('%s','%s', if_not_exists => TRUE, chunk_time_interval => INTERVAL '%s');", table, timeColumn, chunkInterval)
	} else {
		stmt = fmt.Sprintf("SELECT create_hypertable('%s','%s', if_not_exists => TRUE);", table, timeColumn)
	}
	if _, err := ds.ExecContext(ctx, stmt); err != nil {
		return fmt.Errorf("create_hypertable table=%s: %w", table, err)
	}
	logging.Infof(ctx, "[postgres_gorm] hypertable ensured table=%s time_column=%s chunk_interval=%s", table, timeColumn, chunkInterval)
	return nil
}

func (c *PostgresGormComponent) listNames() []string {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	names := make([]string, 0, len(c.dbs))
	for k := range c.dbs {
		names = append(names, k)
	}
	sort.Strings(names)
	return names
}

// buildDSN builds postgres DSN.
func buildDSN(ds *DataSourceConfig) (string, error) {
	if strings.TrimSpace(ds.DSN) != "" {
		return ds.DSN, nil
	}
	if ds.Host == "" || ds.User == "" || ds.Database == "" {
		return "", errors.New("host, user, database required when dsn not provided")
	}
	port := ds.Port
	if port == 0 {
		port = 5432
	}
	params := url.Values{}
	for k, v := range ds.Params {
		params.Set(k, v)
	}
	// standard libpq style DSN for gorm: host=... user=... password=... dbname=... port=... param=...
	base := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%d", ds.Host, ds.User, ds.Password, ds.Database, port)
	var extras []string
	for k, v := range ds.Params {
		extras = append(extras, fmt.Sprintf("%s=%s", k, v))
	}
	if len(extras) > 0 {
		base += " " + strings.Join(extras, " ")
	}
	return base, nil
}

// runGormMigrations same logic as mysql variant.
func runGormMigrations(ctx context.Context, db *sql.DB, dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("read migrations dir: %w", err)
	}
	var files []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.HasSuffix(strings.ToLower(name), ".sql") {
			files = append(files, filepath.Join(dir, name))
		}
	}
	sort.Strings(files)
	for _, f := range files {
		b, err := os.ReadFile(f)
		if err != nil {
			return fmt.Errorf("read %s: %w", f, err)
		}
		stmts := strings.Split(string(b), ";")
		for _, s := range stmts {
			if strings.TrimSpace(s) == "" {
				continue
			}
			if _, err := db.ExecContext(ctx, s); err != nil {
				return fmt.Errorf("exec %s failed: %w", f, err)
			}
		}
	}
	return nil
}

// ensureTimescaleExtension attempts to create timescaledb extension if not exists.
func ensureTimescaleExtension(ctx context.Context, db *sql.DB, schema string) error {
	// timescaledb usually installed in public schema; we allow optional schema override.
	q := "CREATE EXTENSION IF NOT EXISTS timescaledb"
	if strings.TrimSpace(schema) != "" {
		q += " SCHEMA " + schema
	}
	if _, err := db.ExecContext(ctx, q); err != nil {
		return fmt.Errorf("create timescaledb extension: %w", err)
	}
	return nil
}

// Reuse gormLogger from mysql gorm component (identical behavior)

type gormLogger struct {
	logLevel      logger.LogLevel
	slowThreshold time.Duration
}

func newGormLogger(cfg *Config) logger.Interface {
	lvl := logger.Info
	slow := 200 * time.Millisecond
	if cfg != nil {
		if cfg.LogLevel != "" {
			switch strings.ToLower(cfg.LogLevel) {
			case "silent":
				lvl = logger.Silent
			case "error":
				lvl = logger.Error
			case "warn", "warning":
				lvl = logger.Warn
			case "info":
				lvl = logger.Info
			case "debug":
				lvl = logger.Info
			}
		}
		if cfg.SlowThreshold > 0 {
			slow = cfg.SlowThreshold
		}
	}
	return &gormLogger{logLevel: lvl, slowThreshold: slow}
}
func (l *gormLogger) LogMode(level logger.LogLevel) logger.Interface {
	nl := *l
	nl.logLevel = level
	return &nl
}
func (l *gormLogger) Info(ctx context.Context, msg string, data ...interface{}) {
	if l.logLevel >= logger.Info {
		logging.Infof(ctx, "[gorm] "+msg, data...)
	}
}
func (l *gormLogger) Warn(ctx context.Context, msg string, data ...interface{}) {
	if l.logLevel >= logger.Warn {
		logging.Warnf(ctx, "[gorm] "+msg, data...)
	}
}
func (l *gormLogger) Error(ctx context.Context, msg string, data ...interface{}) {
	if l.logLevel >= logger.Error {
		logging.Errorf(ctx, "[gorm] "+msg, data...)
	}
}
func (l *gormLogger) Trace(ctx context.Context, begin time.Time, fc func() (string, int64), err error) {
	if l.logLevel <= logger.Silent {
		return
	}
	elapsed := time.Since(begin)
	sqlStr, rows := fc()
	if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) && l.logLevel >= logger.Error {
		logging.Errorf(ctx, "[gorm] error elapsed=%s rows=%d sql=%s err=%v", elapsed, rows, sqlStr, err)
		return
	}
	if l.slowThreshold > 0 && elapsed > l.slowThreshold && l.logLevel >= logger.Warn {
		logging.Warnf(ctx, "[gorm] slow elapsed=%s threshold=%s rows=%d sql=%s", elapsed, l.slowThreshold, rows, sqlStr)
		return
	}
	if l.logLevel >= logger.Info {
		logging.Debugf(ctx, "[gorm] elapsed=%s rows=%d sql=%s", elapsed, rows, sqlStr)
	}
}
