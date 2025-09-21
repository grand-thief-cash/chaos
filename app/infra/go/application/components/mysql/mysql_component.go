// components/mysql/mysql_component.go
package mysql

import (
	"context"
	"database/sql"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type MysqlComponent struct {
	*core.BaseComponent
	cfg       *MySQLConfig
	databases map[string]*sql.DB
	mutex     sync.RWMutex
}

func NewMySQLComponent(cfg *MySQLConfig) *MysqlComponent {
	return &MysqlComponent{
		BaseComponent: core.NewBaseComponent(consts.COMPONENT_MYSQL),
		cfg:           cfg,
		databases:     make(map[string]*sql.DB),
	}
}

func (c *MysqlComponent) Start(ctx context.Context) error {
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	if c.cfg == nil || !c.cfg.Enabled {
		return fmt.Errorf("mysql component enabled flag mismatch")
	}
	if len(c.cfg.DataSources) == 0 {
		return fmt.Errorf("no mysql data_sources configured")
	}

	for name, ds := range c.cfg.DataSources {
		if ds == nil {
			return fmt.Errorf("datasource %s config is nil", name)
		}
		dsn, err := c.buildDSN(ds)
		if err != nil {
			return fmt.Errorf("build dsn for %s failed: %w", name, err)
		}

		db, err := sql.Open("mysql", dsn)
		if err != nil {
			return fmt.Errorf("open db %s failed: %w", name, err)
		}

		// Pool settings with sane defaults
		if ds.MaxOpenConns > 0 {
			db.SetMaxOpenConns(ds.MaxOpenConns)
		} else {
			db.SetMaxOpenConns(50)
		}
		if ds.MaxIdleConns > 0 {
			db.SetMaxIdleConns(ds.MaxIdleConns)
		} else {
			db.SetMaxIdleConns(10)
		}
		if ds.ConnMaxLife > 0 {
			db.SetConnMaxLifetime(ds.ConnMaxLife)
		} else {
			db.SetConnMaxLifetime(60 * time.Minute)
		}
		if ds.ConnMaxIdle > 0 {
			db.SetConnMaxIdleTime(ds.ConnMaxIdle)
		}

		if ds.PingOnStart {
			pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
			if err := db.PingContext(pingCtx); err != nil {
				cancel()
				_ = db.Close()
				return fmt.Errorf("ping db %s failed: %w", name, err)
			}
			cancel()
		}

		c.mutex.Lock()
		c.databases[name] = db
		c.mutex.Unlock()

		logging.Infof(ctx, "[mysql] datasource %s initialized", name)
	}

	list := c.listNames()
	logging.Infof(ctx, "[mysql] component started. data sources=%v", list)
	return nil
}

func (c *MysqlComponent) Stop(ctx context.Context) error {
	defer c.BaseComponent.Stop(ctx)
	c.mutex.Lock()
	defer c.mutex.Unlock()
	for name, db := range c.databases {
		if db != nil {
			_ = db.Close()
			logging.Infof(ctx, "[mysql] datasource %s closed", name)
		}
	}
	return nil
}

func (c *MysqlComponent) HealthCheck() error {
	if err := c.BaseComponent.HealthCheck(); err != nil {
		return err
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	for name, db := range c.databases {
		if db == nil {
			return fmt.Errorf("datasource %s not initialized", name)
		}
		if err := db.Ping(); err != nil {
			return fmt.Errorf("datasource %s ping failed: %w", name, err)
		}
	}
	return nil
}

// GetDB returns *sql.DB by datasource name.
func (c *MysqlComponent) GetDB(name string) (*sql.DB, error) {
	c.mutex.RLock()
	db, ok := c.databases[name]
	c.mutex.RUnlock()
	if !ok {
		return nil, fmt.Errorf("mysql datasource %s not found", name)
	}
	return db, nil
}

func (c *MysqlComponent) buildDSN(ds *MySQLDataSourceConfig) (string, error) {
	if strings.TrimSpace(ds.DSN) != "" {
		return ds.DSN, nil
	}
	if ds.Host == "" || ds.User == "" || ds.Database == "" {
		return "", fmt.Errorf("host, user, database required when dsn not provided")
	}
	port := ds.Port
	if port == 0 {
		port = 3306
	}

	params := url.Values{}
	// defaults
	params.Set("parseTime", "true")
	params.Set("charset", "utf8mb4")
	params.Set("loc", "Local")

	for k, v := range ds.Params {
		params.Set(k, v)
	}

	pwd := ds.Password
	// DSN format: user:password@tcp(host:port)/dbname?param=val
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?%s",
		ds.User, pwd, ds.Host, port, ds.Database, params.Encode()), nil
}

func (c *MysqlComponent) listNames() []string {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	names := make([]string, 0, len(c.databases))
	for k := range c.databases {
		names = append(names, k)
	}
	sort.Strings(names)
	return names
}
