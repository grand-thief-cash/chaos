package postgresgorm

import (
	"fmt"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type Factory struct{}

func NewFactory() *Factory { return &Factory{} }

// Create expects *postgresgorm.Config.
func (f *Factory) Create(cfg interface{}) (core.Component, error) {
	pgCfg, ok := cfg.(*Config)
	if !ok {
		return nil, fmt.Errorf("invalid config type for postgres gorm component (need *postgresgorm.Config)")
	}
	if pgCfg == nil || !pgCfg.Enabled {
		return nil, fmt.Errorf("postgres gorm component disabled")
	}
	if len(pgCfg.DataSources) == 0 {
		return nil, fmt.Errorf("postgres gorm component has no data_sources")
	}
	return NewPostgresGormComponent(pgCfg), nil
}
