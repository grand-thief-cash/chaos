package model

import (
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// TaskRun 代表一次定时任务的实际运行实例。
// 字段详细说明如下：
type TaskRun struct {
	ID               int64            // 主键 ID，唯一标识一次运行
	TaskID           int64            // 关联的 Task ID，指向所属的定时任务
	ScheduledTime    time.Time        // 计划执行时间（UTC），由调度器分配
	StartTime        *time.Time       // 实际开始时间，任务开始时记录
	EndTime          *time.Time       // 实际结束时间，任务完成时记录
	Status           consts.RunStatus // 运行状态，见 RunStatus 枚举
	Attempt          int              // 当前尝试次数（含重试）
	RequestHeaders   string           // 发送 HTTP 请求时的请求头（JSON 字符串）
	RequestBody      string           // 发送 HTTP 请求时的请求体内容
	ResponseCode     *int             // HTTP 响应码（如有）
	ResponseBody     string           // HTTP 响应体内容（如有）
	ErrorMessage     string           // 错误信息（如有）
	NextRetryTime    *time.Time       // 下次重试时间（如有重试计划）
	CallbackToken    string           // 回调 token，用于异步任务回调识别
	CallbackDeadline *time.Time       // 回调超时时间（异步任务专用）
	TraceID          string           // 链路追踪 ID（如有）
	CreatedAt        time.Time        // 创建时间
	UpdatedAt        time.Time        // 最近更新时间
}

func (TaskRun) TableName() string { return "task_runs" }
