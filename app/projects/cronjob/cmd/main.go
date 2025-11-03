package main

import (
	"context"
	"log"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
	"github.com/grand-thief-cash/chaos/app/infra/go/common/utils/net"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/api"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/registry_ext"
)

var (
	Version = "v0.1.0-phase1"
)

func main() {
	app := application.GetApp()

	hooks.RegisterHook("Service Preparation", hooks.BeforeStart, func(ctx context.Context) error {
		consts.LocalIP, _ = net.GetLocalIP()
		return nil
	}, 1)

	if err := app.Run(); err != nil {
		log.Fatalf("app exited with error: %v", err)
	}
}
