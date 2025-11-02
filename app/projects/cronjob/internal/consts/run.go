package consts

// RunStatus 表示任务运行的状态枚举，防止魔法字符串。
type RunStatus string

const (
	Scheduled       RunStatus = "SCHEDULED"        // 已调度，等待执行
	Running         RunStatus = "RUNNING"          // 正在执行
	Success         RunStatus = "SUCCESS"          // 执行成功
	Failed          RunStatus = "FAILED"           // 执行失败
	Timeout         RunStatus = "TIMEOUT"          // 执行超时
	Retrying        RunStatus = "RETRYING"         // 正在重试
	CallbackPending RunStatus = "CALLBACK_PENDING" // 等待异步回调
	CallbackFailed  RunStatus = "CALLBACK_FAILED"  // 异步回调失败（非超时）
	FailedTimeout   RunStatus = "FAILED_TIMEOUT"   // 回调超时失败
	Canceled        RunStatus = "CANCELED"         // 被取消
	Skipped         RunStatus = "SKIPPED"          // 被跳过
	FailureSkip     RunStatus = "FAILURE_SKIP"     // 因失败跳过
	ConcurrentSkip  RunStatus = "CONCURRENT_SKIP"  // 因并发限制跳过
	OverlapSkip     RunStatus = "OVERLAP_SKIP"     // 因重叠限制跳过
)
