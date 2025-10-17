package autowire_test

import (
	"testing"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/autowire"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/config"
	appconsts "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
	cronConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/registry_ext" // ensure builders registered
)

// minimal config loader (reuse existing config manager)
func loadCfg(t *testing.T) *config.AppConfig {
	cm := config.NewConfigManager("development", "./config/config.yaml")
	if err := cm.LoadConfig(); err != nil {
		// allow test to skip if config missing rather than panic
		t.Fatalf("load config failed: %v", err)
	}
	return cm.GetConfig()
}

func TestAutoBuilderDependencyInferenceAndRuntimeOrdering(t *testing.T) {
	cfg := loadCfg(t)
	c := core.NewContainer()
	if err := registry.BuildAndRegisterAll(cfg, c); err != nil {
		t.Fatalf("build/register failed: %v", err)
	}
	if err := autowire.InjectAll(c); err != nil {
		t.Fatalf("autowire failed: %v", err)
	}
	ordered, err := c.ValidateDependencies()
	if err != nil {
		t.Fatalf("validate deps failed: %v", err)
	}
	idx := map[string]int{}
	for i, comp := range ordered {
		idx[comp.Name()] = i
	}
	// mysql_gorm should appear before daos & executor & scheduler & controller.
	checkBefore := func(a, b string) {
		ia, okA := idx[a]
		ib, okB := idx[b]
		if !okA || !okB {
			return // component not present (maybe disabled); skip
		}
		if ia > ib {
			t.Fatalf("expected %s before %s in start order (topological), got %d > %d", a, b, ia, ib)
		}
	}
	checkBefore(appconsts.COMPONENT_MYSQL_GORM, cronConsts.COMP_DAO_TASK)
	checkBefore(appconsts.COMPONENT_MYSQL_GORM, cronConsts.COMP_DAO_RUN)
	checkBefore(cronConsts.COMP_DAO_TASK, cronConsts.COMP_SVC_EXECUTOR) // executor depends on daos
	checkBefore(cronConsts.COMP_DAO_RUN, cronConsts.COMP_SVC_EXECUTOR)
	checkBefore(cronConsts.COMP_SVC_EXECUTOR, cronConsts.COMP_SVC_SCHEDULER)
}
