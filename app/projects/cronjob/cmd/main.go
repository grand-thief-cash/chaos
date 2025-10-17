package main

import (
	"log"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/api"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	_ "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/registry_ext"
)

var (
	Version = "v0.1.0-phase1"
)

func main() {
	app := application.GetApp()

	if err := app.Run(); err != nil {
		log.Fatalf("app exited with error: %v", err)
	}
}
