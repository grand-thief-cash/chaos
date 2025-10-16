package main

import (
	"log"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
)

var (
	Version = "v0.1.0-phase1"
)

func main() {
	app := application.GetApp()

	if err := app.Run(); err != nil {
		log.Fatalf("app exited with error: %v", err)
	}

	//migrateFlag := flag.Bool("migrate", true, "run SQL migrations on startup")
	//migrationsDir := flag.String("migrations", "migrations", "directory containing *.sql migration files")
	//flag.Parse()
	//
	//cfg, err := config.Load(*cfgPath)
	//if err != nil {
	//	log.Fatalf("load config: %v", err)
	//}
	//
	//gdb, err := dao.OpenMySQL(cfg.MySQL.DSN)
	//if err != nil {
	//	log.Fatalf("open mysql: %v", err)
	//}
	//sqlDB, err := gdb.DB()
	//if err != nil {
	//	log.Fatalf("unwrap sql db: %v", err)
	//}
	//defer sqlDB.Close()
	//
	//if err := dao.Ping(gdb, 5, time.Second*2); err != nil {
	//	log.Fatalf("ping mysql: %v", err)
	//}
	//
	//if *migrateFlag {
	//	abs, _ := filepath.Abs(*migrationsDir)
	//	if err := migrate.Run(context.Background(), sqlDB, abs); err != nil {
	//		log.Fatalf("migrations failed: %v", err)
	//	}
	//	log.Printf("migrations applied from %s", abs)
	//}

	//taskDao := dao.NewTaskDao(gdb)
	//runDao := dao.NewRunDao(gdb)
	//
	//exec := executor.NewExecutor(executor.Config{
	//	WorkerPoolSize: cfg.Executor.WorkerPoolSize,
	//	RequestTimeout: cfg.Executor.RequestTimeout,
	//}, taskDao, runDao)
	//
	//sch := scheduler.NewEngine(taskDao, runDao, exec,
	//	scheduler.Config{PollInterval: cfg.Scheduler.PollInterval})

	//// start background components
	//ctx, cancel := context.WithCancel(context.Background())
	//defer cancel()
	//go sch.Start(ctx)
	//go exec.Start(ctx)

	//router := api.NewRouter(api.Dependencies{
	//	TaskRepo: taskDao,
	//	RunRepo:  runDao,
	//	Exec:     exec,
	//	Sched:    sch,
	//	Version:  Version,
	//})

	//srv := &http.Server{Addr: cfg.Server.Address(), Handler: router, ReadHeaderTimeout: 5 * time.Second}
	//go func() {
	//	log.Printf("cronjob server listening on %s", cfg.Server.Address())
	//	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
	//		log.Fatalf("server error: %v", err)
	//	}
	//}()

}
