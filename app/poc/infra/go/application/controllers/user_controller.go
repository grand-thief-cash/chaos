package controllers

import (
	"database/sql"
	"net/http"

	"github.com/go-chi/chi/v5"

	http_serv "github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	appmysql "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysql"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

func init() {
	http_serv.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		// Resolve MySQL component
		comp, err := c.Resolve("mysql")
		if err != nil {
			return err
		}
		mysqlComp := comp.(*appmysql.MysqlComponent)
		db, err := mysqlComp.GetDB("primary")
		if err != nil {
			return err
		}

		r.Route("/users", func(r chi.Router) {
			r.Get("/{id}", getUserHandler(db))
		})
		return nil
	})
}

func getUserHandler(db *sql.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		_ = id
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("user:" + id))
	}
}
