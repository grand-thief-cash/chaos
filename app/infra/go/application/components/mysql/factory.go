// components/mysql/factory.go
package mysql

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	mysqlCfg, ok := cfg.(*MySQLConfig)
	if !ok {
		return nil, fmt.Errorf("invalid config type for mysql component (need *MySQLConfig)")
	}
	if !mysqlCfg.Enabled {
		return nil, fmt.Errorf("mysql component disabled")
	}
	if len(mysqlCfg.DataSources) == 0 {
		return nil, fmt.Errorf("mysql component has no data_sources")
	}
	return NewMySQLComponent(mysqlCfg), nil
}
