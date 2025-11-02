package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
	"github.com/grand-thief-cash/chaos/app/poc/infra/go/application/config"
	_ "github.com/grand-thief-cash/chaos/app/poc/infra/go/application/config"
	_ "github.com/grand-thief-cash/chaos/app/poc/infra/go/application/services"
)

func main() {
	app := application.GetApp()

	// Optional custom hook
	_ = app.AddHook("custom_after_start", hooks.AfterStart, func(ctx context.Context) error {
		logging.Info(ctx, "Custom after_start hook executed")
		return nil
	}, 200)

	_ = app.AddHook("register_routes", hooks.BeforeStart, func(ctx context.Context) error {
		comp, err := app.GetComponent("http_server")
		if err != nil {
			return err
		}
		hc := comp.(*http_server.HTTPServerComponent)
		return hc.AddRouteRegistrar(func(r chi.Router, c *core.Container) error {
			r.Get("/ping", func(w http.ResponseWriter, req *http.Request) {
				w.WriteHeader(http.StatusOK)
				_, _ = w.Write([]byte("pong"))
			})
			return nil
		})
	}, 100)

	_ = app.AddHook("check biz config", hooks.AfterStart, func(ctx context.Context) error {
		go func() {
			for {
				fmt.Println(fmt.Sprintf("config %v", config.GetBizConfig()))
				time.Sleep(2 * time.Second)
			}
		}()
		return nil
	}, 100)

	// Run in a separate goroutine so we can simulate shutdown
	if err := app.Run(); err != nil {
		log.Fatalf("app exited with error: %v", err)
	}

}
