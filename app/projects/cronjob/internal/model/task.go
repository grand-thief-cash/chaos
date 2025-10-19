package model

import (
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// Task 描述一个可调度的定时任务配置。
type Task struct {
	ID                 int64                    // 主键 ID
	Name               string                   // 任务唯一名称（业务可读标识）
	Description        string                   // 任务说明文字
	CronExpr           string                   // 规范化后的 6 字段 Cron 表达式（秒 分 时 日 月 周）
	Timezone           string                   // 时区（未来用于按配置时区解析 Cron；当前默认 UTC）
	ExecType           consts.ExecType          // 执行类型：SYNC/ASYNC（异步回调暂未实现）
	HTTPMethod         string                   // 下游 HTTP 请求方法，如 GET/POST
	TargetURL          string                   // 下游调用目标 URL（含协议）
	HeadersJSON        string                   // 以 JSON 字符串格式存储的额外请求头
	BodyTemplate       string                   // 请求体模板
	TimeoutSeconds     int                      // 单次执行超时时间（秒）
	RetryPolicyJSON    string                   // 重试策略 JSON（占位，未来使用）
	MaxConcurrency     int                      // 单任务允许运行的最大并发数（<=0 视为不限制）
	ConcurrencyPolicy  consts.ConcurrencyPolicy // 并发策略：QUEUE/SKIP/PARALLEL
	CallbackMethod     string                   // 异步任务回调使用的 HTTP 方法（预留）
	CallbackTimeoutSec int                      // 异步回调等待超时时间
	OverlapAction      consts.OverlapAction     // 上一轮仍未完成时的处理策略
	FailureAction      consts.FailureAction     // 上一轮失败/超时/取消后的处理策略
	Status             consts.TaskStatus        // 任务状态：ENABLED / DISABLED
	Version            int                      // 乐观锁版本（更新时 +1）
	CreatedAt          time.Time                // 创建时间
	UpdatedAt          time.Time                // 最近更新时间
	Deleted            int                      // 软删除标志位：0 未删除，1 已删除
}

// NormalizeCron 规范化 Cron 表达式：如果是 5 字段则自动补前导秒 0
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

func (Task) TableName() string { return "tasks" }
