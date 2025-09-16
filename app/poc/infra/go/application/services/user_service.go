package services

import (
	"database/sql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type UserService struct{ db *sql.DB }

func NewUserService(c *core.Container) (*UserService, error) {
	comp, _ := c.Resolve("mysql")
	ds, _ := comp.(*mysql.MysqlComponent).GetDB("primary")
	return &UserService{db: ds}, nil
}
