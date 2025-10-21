package api

import (
	"fmt"
	"math/rand"
	"net/http"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type POCController struct {
	*core.BaseComponent
}

func NewPOCController() *POCController {
	return &POCController{BaseComponent: core.NewBaseComponent("poc_ctrl", consts.COMPONENT_LOGGING)}
}

func (tmc *POCController) giveAnswer(w http.ResponseWriter, r *http.Request) {
	res := make(map[string]interface{})
	randNum := rand.Int31n(13)
	logging.Info(r.Context(), fmt.Sprintf("sleeping for %d seconds", randNum))
	time.Sleep(time.Duration(randNum) * time.Second)
	res["result"] = time.Now().Unix()
	writeJSON(w, res)
}
