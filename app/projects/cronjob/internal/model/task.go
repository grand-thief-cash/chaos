package model

import (
	"strings"
	"time"

	"github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// ExecType 表示任务执行类型：同步 (SYNC) 或 异步 (ASYNC)

// Task 描述一个可调度的定时任务配置，字段已按当前 Phase1 / 规划中的未来能力预留。
type Task struct {
	ID                 int64                    // 主键 ID
	Name               string                   // 任务唯一名称（业务可读标识）
	Description        string                   // 任务说明文字
	CronExpr           string                   // 规范化后的 6 字段 Cron 表达式（秒 分 时 日 月 周）
	Timezone           string                   // 时区（未来用于按配置时区解析 Cron；当前默认 UTC）
	ExecType           consts.ExecType          // 执行类型：SYNC/ASYNC（异步回调暂未实现）
	HTTPMethod         string                   // 下游 HTTP 请求方法，如 GET/POST
	TargetURL          string                   // 下游调用目标 URL（含协议）
	HeadersJSON        string                   // 以 JSON 字符串形式存储的额外请求头 (map[string]string)
	BodyTemplate       string                   // 请求体模板（未来可支持变量渲染；当前原样发送）
	TimeoutSeconds     int                      // 单次执行超时时间（秒）
	RetryPolicyJSON    string                   // 重试策略 JSON（占位，Phase2 实现，例如 {max_retries,...}）
	MaxConcurrency     int                      // 单任务允许运行的最大并发数（<=0 视为不限制）
	ConcurrencyPolicy  consts.ConcurrencyPolicy // 并发策略：QUEUE/SKIP/PARALLEL
	MisfirePolicy      consts.MisfirePolicy     // Misfire 策略占位（FIRE_NOW/SKIP/CATCH_UP_LIMITED，尚未实现）
	CatchupLimit       int                      // Misfire 追赶的最大次数（MisfirePolicy=CATCH_UP_LIMITED 时使用）
	CallbackMethod     string                   // 异步任务回调使用的 HTTP 方法（预留）
	CallbackTimeoutSec int                      // 异步回调等待超时时间（秒，预留）
	Status             consts.TaskStatus        // 任务状态：ENABLED / DISABLED
	Version            int                      // 乐观锁版本（更新时 +1，用于并发修改控制）
	CreatedAt          time.Time                // 创建时间
	UpdatedAt          time.Time                // 最近更新时间
	Deleted            int                      // 软删除标志位：0 表示未删除，1 表示已删除
}

// NormalizeCron ���准化 Cron 表达式：如果是 5 字段则自动补前导秒 0
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
