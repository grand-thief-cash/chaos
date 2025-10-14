package model

import (
	"strings"
	"time"
)

type ExecType string

const (
	ExecTypeSync  ExecType = "SYNC"
	ExecTypeAsync ExecType = "ASYNC"
)

type ConcurrencyPolicy string

const (
	ConcurrencyQueue    ConcurrencyPolicy = "QUEUE"
	ConcurrencySkip     ConcurrencyPolicy = "SKIP"
	ConcurrencyParallel ConcurrencyPolicy = "PARALLEL"
)

type Task struct {
	ID                 int64
	Name               string
	Description        string
	CronExpr           string // normalized 6-field
	Timezone           string
	ExecType           ExecType
	HTTPMethod         string
	TargetURL          string
	HeadersJSON        string
	BodyTemplate       string
	TimeoutSeconds     int
	RetryPolicyJSON    string
	MaxConcurrency     int
	ConcurrencyPolicy  ConcurrencyPolicy
	MisfirePolicy      string
	CatchupLimit       int
	CallbackMethod     string
	CallbackTimeoutSec int
	Status             string
	Version            int
	CreatedAt          time.Time
	UpdatedAt          time.Time
}

func NormalizeCron(expr string) string {
	parts := strings.Fields(expr)
	if len(parts) == 5 { // prepend 0 seconds
		return "0 " + expr
	}
	if len(parts) == 6 {
		return expr
	}
	return expr // invalid left as is, will fail validation
}
