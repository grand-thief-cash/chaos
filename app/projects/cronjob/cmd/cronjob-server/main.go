package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/api"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/config"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/executor"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/migrate"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/repository"
	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/scheduler"
)

var (
	Version = "v0.1.0-phase1"
)

func main() {
	cfgPath := flag.String("config", "config.yaml", "config file path")
	migrateFlag := flag.Bool("migrate", true, "run SQL migrations on startup")
	migrationsDir := flag.String("migrations", "migrations", "directory containing *.sql migration files")
	flag.Parse()

	cfg, err := config.Load(*cfgPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	db, err := repository.OpenMySQL(cfg.MySQL.DSN)
	if err != nil {
		log.Fatalf("open mysql: %v", err)
	}
	defer db.Close()

	if err := repository.Ping(db, 5, time.Second*2); err != nil {
		log.Fatalf("ping mysql: %v", err)
	}

	if *migrateFlag {
		abs, _ := filepath.Abs(*migrationsDir)
		if err := migrate.Run(context.Background(), db, abs); err != nil {
			log.Fatalf("migrations failed: %v", err)
		}
		log.Printf("migrations applied from %s", abs)
	}

	taskRepo := repository.NewTaskRepository(db)
	runRepo := repository.NewRunRepository(db)

	exec := executor.NewExecutor(executor.Config{
		WorkerPoolSize: cfg.Executor.WorkerPoolSize,
		RequestTimeout: cfg.Executor.RequestTimeout,
	}, taskRepo, runRepo)

	sch := scheduler.NewEngine(taskRepo, runRepo, exec,
		scheduler.Config{PollInterval: cfg.Scheduler.PollInterval})

	// start background components
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go sch.Start(ctx)
	go exec.Start(ctx)

	router := api.NewRouter(api.Dependencies{
		TaskRepo: taskRepo,
		RunRepo:  runRepo,
		Exec:     exec,
		Sched:    sch,
		Version:  Version,
	})

	srv := &http.Server{Addr: cfg.Server.Address(), Handler: router, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		log.Printf("cronjob server listening on %s", cfg.Server.Address())
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh
	log.Println("shutdown signal received")

	shutdownCtx, cancel2 := context.WithTimeout(context.Background(), cfg.Server.GracefulTimeout)
	defer cancel2()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("graceful shutdown failed: %v", err)
	}
	log.Println("server exited")
}
