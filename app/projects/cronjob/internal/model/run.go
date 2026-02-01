package model

import (
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// TaskRun 代表一次定时任务的实际运行实例。
// 字段详细说明如下：
type TaskRun struct {
	ID                 int64            `json:"id"`                            // 主键 ID，唯一标识一次运行
	TaskID             int64            `json:"task_id"`                       // 关联的 Task ID，指向所属的定时任务
	ScheduledTime      time.Time        `json:"scheduled_time"`                // 计划执行时间（UTC），由调度器分配
	StartTime          *time.Time       `json:"start_time"`                    // 实际开始时间，任务开始时记录
	EndTime            *time.Time       `json:"end_time"`                      // 实际结束时间，任务完成时记录
	Status             consts.RunStatus `json:"status"`                        // 运行状态，见 RunStatus 枚举
	Attempt            int              `json:"attempt"`                       // 当前尝试次数（含重试）
	TargetService      string           `json:"target_service"`                // 目标服务标识 (e.g. "artemis")
	TargetPath         string           `json:"target_path"`                   // 目标路径 (e.g. "/api/v1/trigger")
	Method             string           `json:"method"`                        // HTTP 方法 (GET/POST)
	ExecType           consts.ExecType  `json:"exec_type"`                     // 执行类型：SYNC/ASYNC
	CallbackTimeoutSec int              `json:"callback_timeout_sec" gorm:"-"` // 异步回调超时时间(秒) - 从Task快照，不入库
	RequestHeaders     string           `json:"request_headers"`               // 发送 HTTP 请求时的请求头（JSON 字符串）
	RequestBody        string           `json:"request_body"`                  // 发送 HTTP 请求时的请求体内容
	ResponseCode       *int             `json:"response_code"`                 // HTTP 响应码（如有）
	ResponseBody       string           `json:"response_body"`                 // HTTP 响应体内容（如有）
	ErrorMessage       string           `json:"error_message"`                 // 错误信息（如有）
	NextRetryTime      *time.Time       `json:"next_retry_time"`               // 下次重试时间（如有重试计划）
	CallbackToken      string           `json:"callback_token"`                // 回调 token，用于异步任务回调识别
	CallbackDeadline   *time.Time       `json:"callback_deadline"`             // 回调超时时间（异步任务专用）
	TraceID            string           `json:"trace_id"`                      // 链路追踪 ID（如有）
	CreatedAt          time.Time        `json:"created_at"`                    // 创建时间
	UpdatedAt          time.Time        `json:"updated_at"`                    // 最近更新时间
}

func (TaskRun) TableName() string { return "task_runs" }
