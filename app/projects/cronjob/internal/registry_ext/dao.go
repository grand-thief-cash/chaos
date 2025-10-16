package registry_ext

import (
	"fmt"

	mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/dao"
)

func init() {
	// RegisterWithDeps 确保构建顺序：mysql_gorm/logging 先被构建并注册
	registry.RegisterWithDeps("task_dao", []string{
		consts.COMPONENT_MYSQL_GORM,
		consts.COMPONENT_LOGGING,
	}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		// 1. 可选启用判断（这里简单直接启用）
		// 2. 构建期 Resolve：拿到尚未启动但已构造的 mysql_gorm 组件实例
		comp, err := c.Resolve(consts.COMPONENT_MYSQL_GORM)
		if err != nil {
			return true, nil, fmt.Errorf("resolve mysql_gorm failed: %w", err)
		}
		gormComp, ok := comp.(*mg.GormComponent)
		if !ok {
			return true, nil, fmt.Errorf("mysql_gorm type assertion failed")
		}
		// 3. 仅注入引用，不获取具体 *gorm.DB（必须留到 Start 之后）
		taskDao := dao.NewTaskDao(gormComp, "cronjob")
		return true, taskDao, nil
	})

	// run_dao builder
	registry.RegisterWithDeps("run_dao", []string{
		consts.COMPONENT_MYSQL_GORM,
		consts.COMPONENT_LOGGING,
	}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
		comp, err := c.Resolve(consts.COMPONENT_MYSQL_GORM)
		if err != nil {
			return true, nil, fmt.Errorf("resolve mysql_gorm failed: %w", err)
		}
		gormComp, ok := comp.(*mg.GormComponent)
		if !ok {
			return true, nil, fmt.Errorf("mysql_gorm type assertion failed")
		}
		runDao := dao.NewRunDao(gormComp, "cronjob")
		return true, runDao, nil
	})
}
