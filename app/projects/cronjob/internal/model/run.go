package model

import "time"

// TaskRun 代表一次定时任务的实际运行实例。
// 字段详细说明如下：
type TaskRun struct {
	ID               int64      // 主键 ID，唯一标识一次运行
	TaskID           int64      // 关联的 Task ID，指向所属的定时任务
	ScheduledTime    time.Time  // 计划执行时间（UTC），由调度器分配
	StartTime        *time.Time // 实际开始时间，任务开始时记录
	EndTime          *time.Time // 实际结束时间，任务完成时记录
	Status           RunStatus  // 运行状态，见 RunStatus 枚举
	Attempt          int        // 当前尝试次数（含重试）
	RequestHeaders   string     // 发送 HTTP 请求时的请求头（JSON 字符串）
	RequestBody      string     // 发送 HTTP 请求时的请求体内容
	ResponseCode     *int       // HTTP 响应码（如有）
	ResponseBody     string     // HTTP 响应体内容（如有）
	ErrorMessage     string     // 错误信息（如有）
	NextRetryTime    *time.Time // 下次重试时间（如有重试计划）
	CallbackToken    string     // 回调 token，用于异步任务回调识别
	CallbackDeadline *time.Time // 回调超时时间（异步任务专用）
	TraceID          string     // 链路追踪 ID（如有）
	CreatedAt        time.Time  // 创建时间
	UpdatedAt        time.Time  // 最近更新时间
}

// RunStatus 表示任务运行的状态枚举，防止魔法字符串。
type RunStatus string

const (
	RunStatusScheduled       RunStatus = "SCHEDULED"        // 已调度，等待执行
	RunStatusRunning         RunStatus = "RUNNING"          // 正在执行
	RunStatusSuccess         RunStatus = "SUCCESS"          // 执行成功
	RunStatusFailed          RunStatus = "FAILED"           // 执行失败
	RunStatusTimeout         RunStatus = "TIMEOUT"          // 执行超时
	RunStatusRetrying        RunStatus = "RETRYING"         // 正在重试
	RunStatusCallbackPending RunStatus = "CALLBACK_PENDING" // 等待异步回调
	RunStatusCallbackSuccess RunStatus = "CALLBACK_SUCCESS" // 异步回调成功
	RunStatusFailedTimeout   RunStatus = "FAILED_TIMEOUT"   // 回调超时失败
	RunStatusCanceled        RunStatus = "CANCELED"         // 被取消
	RunStatusSkipped         RunStatus = "SKIPPED"          // 被跳过
)

func (TaskRun) TableName() string { return "task_runs" }
