package dao

import (
	"time"

	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

// OpenMySQL opens a GORM *gorm.DB connection using the given DSN.
func OpenMySQL(dsn string) (*gorm.DB, error) {
	cfg := &gorm.Config{}
	return gorm.Open(mysql.Open(dsn), cfg)
}

// Ping retries Ping on the underlying *sql.DB of a *gorm.DB.
func Ping(gdb *gorm.DB, attempts int, interval time.Duration) error {
	sqlDB, err := gdb.DB()
	if err != nil {
		return err
	}
	for i := 0; i < attempts; i++ {
		if err := sqlDB.Ping(); err != nil {
			time.Sleep(interval)
			continue
		}
		return nil
	}
	return sqlDB.Ping()
}
