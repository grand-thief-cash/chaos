// go
package mysqlgorm

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	mysqlDriver "gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// GormComponent manages one GORM *gorm.DB per datasource (single underlying sql.DB pool).
type GormComponent struct {
	*core.BaseComponent
	cfg   *Config
	dbs   map[string]*gorm.DB
	mutex sync.RWMutex
	log   logger.Interface
}

func NewGormComponent(cfg *Config) *GormComponent {
	gc := &GormComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_MYSQL_GORM, consts.COMPONENT_LOGGING), // add explicit logging dependency
		cfg:           cfg,
		dbs:           make(map[string]*gorm.DB),
	}
	gc.log = newGormLogger(cfg)
	return gc
}

func (c *GormComponent) Start(ctx context.Context) error {
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if c.cfg == nil || !c.cfg.Enabled {
		return fmt.Errorf("mysql_gorm component disabled or nil config")
	}
	if len(c.cfg.DataSources) == 0 {
		return fmt.Errorf("mysql_gorm no data_sources configured")
	}

	for name, ds := range c.cfg.DataSources {
		if ds == nil {
			return fmt.Errorf("datasource %s config is nil", name)
		}
		dsn, err := buildDSN(ds)
		if err != nil {
			return fmt.Errorf("build dsn for %s failed: %w", name, err)
		}

		gormDB, err := gorm.Open(mysqlDriver.New(mysqlDriver.Config{DSN: dsn}), &gorm.Config{
			Logger:                                   c.log,
			SkipDefaultTransaction:                   ds.SkipDefaultTransaction,
			PrepareStmt:                              ds.PrepareStmt,
			DisableForeignKeyConstraintWhenMigrating: true,
		})
		if err != nil {
			return fmt.Errorf("open gorm db %s failed: %w", name, err)
		}

		sqlDB, err := gormDB.DB()
		if err != nil {
			return fmt.Errorf("get underlying sql.DB for %s failed: %w", name, err)
		}

		// Pool settings
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
				return fmt.Errorf("ping gorm db %s failed: %w", name, err)
			}
			cancel()
		}

		c.mutex.Lock()
		c.dbs[name] = gormDB
		c.mutex.Unlock()

		logging.Infof(ctx, "[mysql_gorm] datasource %s initialized", name)
	}
	logging.Infof(ctx, "[mysql_gorm] started. data sources=%v", c.listNames())
	return nil
}

func (c *GormComponent) Stop(ctx context.Context) error {
	// BaseComponent.Stop 目前总返回 nil，这里显式调用并忽略返回以避免 lint 警告。
	defer func() { _ = c.BaseComponent.Stop(ctx) }()
	c.mutex.Lock()
	defer c.mutex.Unlock()
	for name, gdb := range c.dbs {
		if gdb != nil {
			if sqlDB, err := gdb.DB(); err == nil {
				_ = sqlDB.Close()
			}
			logging.Infof(ctx, "[mysql_gorm] datasource %s closed", name)
		}
	}
	return nil
}

func (c *GormComponent) HealthCheck() error {
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

func (c *GormComponent) GetDB(name string) (*gorm.DB, error) {
	c.mutex.RLock()
	db, ok := c.dbs[name]
	c.mutex.RUnlock()
	if !ok {
		return nil, fmt.Errorf("mysql_gorm datasource %s not found", name)
	}
	return db, nil
}

func (c *GormComponent) listNames() []string {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	names := make([]string, 0, len(c.dbs))
	for k := range c.dbs {
		names = append(names, k)
	}
	sort.Strings(names)
	return names
}

// buildDSN builds DSN from datasource pieces if DSN not provided.
func buildDSN(ds *DataSourceConfig) (string, error) {
	if strings.TrimSpace(ds.DSN) != "" {
		return ds.DSN, nil
	}
	if ds.Host == "" || ds.User == "" || ds.Database == "" {
		return "", errors.New("host, user, database required when dsn not provided")
	}
	port := ds.Port
	if port == 0 {
		port = 3306
	}
	params := url.Values{}
	params.Set("parseTime", "true")
	params.Set("charset", "utf8mb4")
	params.Set("loc", "Local")
	for k, v := range ds.Params {
		params.Set(k, v)
	}
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?%s", ds.User, ds.Password, ds.Host, port, ds.Database, params.Encode()), nil
}

// GORM logger implementation

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
				lvl = logger.Info // GORM doesn't have debug separate; use Info and we map to Debugf in Trace path.
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
