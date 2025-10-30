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
  | 'CALLBACK_SUCCESS'
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
  http_method: string;
  target_url: string;
  headers_json: string;
  body_template: string;
  timeout_seconds: number;
  retry_policy_json: string;
  max_concurrency: number;
  concurrency_policy: 'SKIP' | 'PARALLEL' | string; // server may extend
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
