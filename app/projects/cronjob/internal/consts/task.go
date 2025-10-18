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

type ExecType string

const (
	ExecTypeSync  ExecType = "SYNC"  // 同步执行：一次 HTTP 请求完成后立即得到结果
	ExecTypeAsync ExecType = "ASYNC" // 异步执行：初始请求后等待回调（Phase2 实现）
)

type MisfirePolicy string

const (
	MisfireFireNow        MisfirePolicy = "FIRE_NOW"         // 立即执行错过的任务
	MisfireSkip           MisfirePolicy = "SKIP"             // 跳过错过的任务
	MisfireCatchUpLimited MisfirePolicy = "CATCH_UP_LIMITED" // 按配置次数追赶执行错过的任务
)

const (
	DEFAULT_JSON_STR = "{}"
)
