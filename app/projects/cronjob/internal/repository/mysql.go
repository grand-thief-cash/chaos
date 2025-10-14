package repository

import (
	"database/sql"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func OpenMySQL(dsn string) (*sql.DB, error) {
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	return db, nil
}

func Ping(db *sql.DB, attempts int, interval time.Duration) error {
	for i := 0; i < attempts; i++ {
		if err := db.Ping(); err != nil {
			time.Sleep(interval)
			continue
		}
		return nil
	}
	return db.Ping()
}
