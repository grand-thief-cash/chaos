// Adjust model to match Go backend API structures (Task, TaskRun)
export type TaskStatus = 'ENABLED' | 'DISABLED';
export type RunStatus =
  | 'SCHEDULED'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'TIMEOUT'
  | 'RETRYING'
  | 'CALLBACK_PENDING'
  | 'FAILED_TIMEOUT'
  | 'CANCELED'
  | 'SKIPPED'
  | 'FAILURE_SKIP'
  | 'CONCURRENT_SKIP'
  | 'OVERLAP_SKIP';

export interface Task {
  id: number;
  name: string;
  description: string;
  cron_expr: string;
  timezone: string;
  exec_type: 'SYNC' | 'ASYNC';
  method: string; // 新增，替代 http_method
  target_service: string; // 新增，服务标识
  target_path: string; // 新增，请求路径
  headers_json: string;
  body_template: string;
  retry_policy_json: string;
  max_concurrency: number;
  concurrency_policy: 'SKIP' | 'PARALLEL' | string;
  callback_method: string;
  callback_timeout_sec: number;
  overlap_action: string;
  failure_action: string;
  status: TaskStatus;
  version: number;
  created_at: string;
  updated_at: string;
  deleted: number;
}

export interface TaskRun {
  id: number;
  task_id: number;
  scheduled_time: string;
  start_time?: string | null;
  end_time?: string | null;
  status: RunStatus;
  attempt: number;
  request_headers: string;
  request_body: string;
  response_code?: number | null;
  response_body: string;
  error_message: string;
  next_retry_time?: string | null;
  callback_token: string;
  callback_deadline?: string | null;
  trace_id: string;
  created_at: string;
  updated_at: string;
}

// Frontend derived presentation models
export interface TaskSummary extends Task {
  // Add computed fields optionally later
}

export interface RunSummary extends TaskRun {}

export interface RunProgress {
  run_id: number;
  percent: number;
  message?: string;
  current?: number;
  total?: number;
}

export interface TaskRunStats {
  task_id: number;
  total_runs: number;
  status_distribution: Record<string, number>;
  status_ratios: Record<string, number>;
  avg_wait_ms: number;
  avg_exec_ms: number;
  sample_size: number;
}

export interface RunsSummaryAggregate {
  total_runs: number;
  status_distribution: Record<string, number>;
  terminal_ratio_estimate?: number;
}
export interface RunsSummaryResponse {
  counts: Record<string, number>;
  aggregates: Record<string, RunsSummaryAggregate>;
}

export type CleanupMode = 'age' | 'count' | 'ids';
export interface CleanupAgeRequest {
  mode: 'age';
  task_id?: number;
  max_age_seconds: number;
}
export interface CleanupCountRequest {
  mode: 'count';
  task_id?: number;
  keep: number;
}
export interface CleanupIdsRequest {
  mode: 'ids';
  ids: number[];
}
export type CleanupRequest = CleanupAgeRequest | CleanupCountRequest | CleanupIdsRequest;
