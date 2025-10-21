package main

import (
	"log"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	// trigger controller + route registration via init()
	_ "github.com/grand-thief-cash/chaos/app/poc/projects/cronjob/internal/api"
	_ "github.com/grand-thief-cash/chaos/app/poc/projects/cronjob/internal/registry_ext"
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
