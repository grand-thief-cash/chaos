package mysqlgorm

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

// Create expects *mysqlgorm.Config.
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	gormCfg, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for gorm component (need *mysqlgorm.Config)")
	}
	if gormCfg == nil || !gormCfg.Enabled {
		return nil, fmt.Errorf("mysql gorm component disabled")
	}
	if len(gormCfg.DataSources) == 0 {
		return nil, fmt.Errorf("mysql gorm component has no data_sources")
	}
	return NewGormComponent(gormCfg), nil
}
