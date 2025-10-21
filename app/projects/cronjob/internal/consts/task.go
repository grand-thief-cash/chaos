package consts

type TaskStatus string

const (
	ENABLED  TaskStatus = "ENABLED"
	DISABLED TaskStatus = "DISABLED"
)

// ConcurrencyPolicy 并发策略
// QUEUE: 达到并发上限时排队（不再新建新的 scheduled，保留已有排队的 scheduled）
// SKIP: 达到并发上限时直接跳过该触发
// PARALLEL: 忽略并发上限（仅使用全局 worker 池大小限制）
type ConcurrencyPolicy string

const (
	ConcurrencySkip     ConcurrencyPolicy = "SKIP"
	ConcurrencyParallel ConcurrencyPolicy = "PARALLEL"
)

// OverlapAction 表示当下一次触发时间到达时，之前是否已有未完成（RUNNING 或 SCHEDULED 排队）的实例存在时的处理策略
// ALLOW: 按并发策略继续判断（如果达到并发上限再按 ConcurrencyPolicy 处理）
// SKIP: 直接跳过本次触发并记录 SKIPPED Run
// CANCEL_PREV: 取消上一轮 RUNNING（若仍 RUNNING），并启动新一轮；若只是排队的 SCHEDULED 不取消，直接新建
// PARALLEL: 忽略并发上限直接并行（覆盖 ConcurrencyPolicy=SKIP/QUEUE 的限制）
type OverlapAction string

const (
	OverlapActionAllow      OverlapAction = "ALLOW"
	OverlapActionSkip       OverlapAction = "SKIP"
	OverlapActionCancelPrev OverlapAction = "CANCEL_PREV"
	OverlapActionParallel   OverlapAction = "PARALLEL"
)

// FailureAction 针对最近一次“有效执行”(非 SKIPPED / SCHEDULED) 失败 (FAILED / TIMEOUT / FAILED_TIMEOUT / CANCELED) 时的策略
// RUN_NEW: 正常启动新一轮（Attempt 重置为 1）
// SKIP: 跳过本次调度并记录 SKIPPED（不会改变失败那一次的基准，下一次仍会看到失败状态，只跳过一次）
// RETRY: 视为重试，新建 Run，Attempt = 上一次 Attempt + 1
type FailureAction string

const (
	FailureActionRunNew FailureAction = "RUN_NEW"
	FailureActionSkip   FailureAction = "SKIP"
	FailureActionRetry  FailureAction = "RETRY"
)

// ExecType 执行类型
// SYNC: 同步执行
// ASYNC: 异步执行（回调 Phase2）
type ExecType string

const (
	ExecTypeSync  ExecType = "SYNC"
	ExecTypeAsync ExecType = "ASYNC"
)

const (
	DEFAULT_JSON_STR                     = "{}"
	DEFAULT_OVERLAP_ACTION OverlapAction = OverlapActionAllow
	DEFAULT_FAILURE_ACTION FailureAction = FailureActionRunNew
)
