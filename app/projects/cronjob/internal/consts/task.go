package consts

type TaskStatus string

const (
	ENABLED  TaskStatus = "ENABLED"
	DISABLED TaskStatus = "DISABLED"
)

// ConcurrencyPolicy 并发策略
type ConcurrencyPolicy string

const (
	ConcurrencyQueue    ConcurrencyPolicy = "QUEUE"    // 达到并发上限时排队等待执行
	ConcurrencySkip     ConcurrencyPolicy = "SKIP"     // 达到并发上限时直接跳过该任务
	ConcurrencyParallel ConcurrencyPolicy = "PARALLEL" //不限制并发，任务可直接并行执行
)

// OverlapAction 表示当下一次触发时间到达时，上一轮仍在运行的处理策略
// ALLOW: 按原有并发策略继续（与 ConcurrencyPolicy 结合）；
// SKIP: 跳过本次触发并记录一次 SKIPPED Run；
// CANCEL_PREV: 取消上一轮（若仍 RUNNING）并启动新一轮；
// PARALLEL: 忽略并发上限直接并行（覆盖 ConcurrencyPolicy=SKIP/QUEUE 的限制）
// NOTE: PARALLEL 实际是强制允许重叠，与 ConcurrencyParallel 类似，但只针对“上一轮未结束”的情形。
// 如果未来需要更细粒度再扩展。
type OverlapAction string

const (
	OverlapAllow      OverlapAction = "ALLOW"
	OverlapSkip       OverlapAction = "SKIP"
	OverlapCancelPrev OverlapAction = "CANCEL_PREV"
	OverlapParallel   OverlapAction = "PARALLEL"
)

// FailureAction 针对上一轮失败 (FAILED / TIMEOUT / FAILED_TIMEOUT / CANCELED) 时的策略
// RUN_NEW: 正常启动新一轮（默认）
// SKIP: 跳过本次调度并记录 SKIPPED
// RETRY: 视为重试，新建一个 Run，Attempt=上一轮+1
// （后续可扩展如 BACKOFF 等）
type FailureAction string

const (
	FailureRunNew FailureAction = "RUN_NEW"
	FailureSkip   FailureAction = "SKIP"
	FailureRetry  FailureAction = "RETRY"
)

// ExecType 执行类型
type ExecType string

const (
	ExecTypeSync  ExecType = "SYNC"  // 同步执行：一次 HTTP 请求完成后立即得到结果
	ExecTypeAsync ExecType = "ASYNC" // 异步执行：初始请求后等待回调（Phase2 实现）
)

// MisfirePolicy 原有策略保持，后续与 Overlap/FailureAction 在调度阶段组合
type MisfirePolicy string

const (
	MisfireFireNow        MisfirePolicy = "FIRE_NOW"         // 立即执行错过的任务
	MisfireSkip           MisfirePolicy = "SKIP"             // 跳过错过的任务
	MisfireCatchUpLimited MisfirePolicy = "CATCH_UP_LIMITED" // 按配置次数追赶执行错过的任务
)

const (
	DEFAULT_JSON_STR = "{}"
	// 默认策略常量
	DEFAULT_OVERLAP_ACTION OverlapAction = OverlapAllow
	DEFAULT_FAILURE_ACTION FailureAction = FailureRunNew
)
