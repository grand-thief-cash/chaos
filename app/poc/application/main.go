package main

import (
	"log"

	"github.com/grand-thief-cash/chaos/app/infra/go/application"
)

func main() {
	//configPath, err := filepath.Rel(".", "./config.yaml")
	//if err != nil {
	//	log.Fatalf("failed to get absolute path: %v", err)
	//}
	//ctx := context.Background()
	app := application.NewApp("development", "C:\\Users\\gaoc3\\projects\\chaos\\app\\poc\\application\\config.yaml")

	// Optional custom hook
	//_ = app.AddHook("custom_after_start", hooks.AfterStart, func(ctx context.Context) error {
	//	logging.Info(ctx, "Custom after_start hook executed")
	//	return nil
	//}, 200)

	// Run in a separate goroutine so we can simulate shutdown
	if err := app.Run(); err != nil {
		log.Fatalf("app exited with error: %v", err)
	}

	// Demo: stop after 5 seconds
	//time.Sleep(20 * time.Second)
	//logging.Info(ctx, "Application started!!!")

	// 从app 中获取mysql 然后列出mysql 建立的链接有哪些数据库：

	//app.Shutdown(ctx)
}
