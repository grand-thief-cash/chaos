package mysqlgorm

import (
	"fmt"

	mysqlComp "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

// Create expects *mysql.MySQLConfig. Reuses same config struct to avoid duplication.
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	mysqlCfg, ok := cfg.(*mysqlComp.MySQLConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for gorm component (need *MySQLConfig)")
	}
	if !mysqlCfg.Enabled {
		return nil, fmt.Errorf("mysql gorm component disabled")
	}
	if len(mysqlCfg.DataSources) == 0 {
		return nil, fmt.Errorf("mysql gorm component has no data_sources")
	}
	return NewGormComponent(mysqlCfg), nil
}
