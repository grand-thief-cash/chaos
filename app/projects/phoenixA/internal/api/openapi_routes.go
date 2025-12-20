package api

import (
	"net/http"
	"os"
	"path/filepath"

	"github.com/go-chi/chi/v5"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/http_server"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

// Expose OpenAPI spec as a static file so tools can discover it.
// - GET /openapi.yaml
func init() {
	http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
		r.Get("/openapi.yaml", func(w http.ResponseWriter, req *http.Request) {
			// Try best-effort to find phoenixA/openapi.yaml based on current working directory.
			// In this repo, phoenixA is typically run with working dir app/projects/phoenixA.
			candidates := []string{
				"openapi.yaml",
				filepath.Join("app", "projects", "phoenixA", "openapi.yaml"),
				filepath.Join(".", "app", "projects", "phoenixA", "openapi.yaml"),
			}
			var data []byte
			var err error
			for _, p := range candidates {
				if _, stErr := os.Stat(p); stErr == nil {
					data, err = os.ReadFile(p)
					break
				}
			}
			if err != nil || data == nil {
				w.WriteHeader(http.StatusNotFound)
				_, _ = w.Write([]byte("openapi.yaml not found"))
				return
			}
			w.Header().Set("Content-Type", "application/yaml")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(data)
		})
		return nil
	})
}
