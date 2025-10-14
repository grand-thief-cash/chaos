package model

import "time"

type RunStatus string

const (
	RunStatusScheduled       RunStatus = "SCHEDULED"
	RunStatusRunning         RunStatus = "RUNNING"
	RunStatusSuccess         RunStatus = "SUCCESS"
	RunStatusFailed          RunStatus = "FAILED"
	RunStatusTimeout         RunStatus = "TIMEOUT"
	RunStatusRetrying        RunStatus = "RETRYING"
	RunStatusCallbackPending RunStatus = "CALLBACK_PENDING"
	RunStatusCallbackSuccess RunStatus = "CALLBACK_SUCCESS"
	RunStatusFailedTimeout   RunStatus = "FAILED_TIMEOUT"
	RunStatusCanceled        RunStatus = "CANCELED"
	RunStatusSkipped         RunStatus = "SKIPPED"
)

type TaskRun struct {
	ID               int64
	TaskID           int64
	ScheduledTime    time.Time
	StartTime        *time.Time
	EndTime          *time.Time
	Status           RunStatus
	Attempt          int
	RequestHeaders   string
	RequestBody      string
	ResponseCode     *int
	ResponseBody     string
	ErrorMessage     string
	NextRetryTime    *time.Time
	CallbackToken    string
	CallbackDeadline *time.Time
	TraceID          string
	CreatedAt        time.Time
	UpdatedAt        time.Time
}
