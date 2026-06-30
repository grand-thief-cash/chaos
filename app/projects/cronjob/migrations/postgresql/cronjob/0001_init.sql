-- Migration: initial schema (merged with client refactor) - PostgreSQL version

-- Create ENUM types for PostgreSQL
CREATE TYPE exec_type_enum AS ENUM ('SYNC', 'ASYNC');
CREATE TYPE concurrency_policy_enum AS ENUM ('QUEUE', 'SKIP', 'PARALLEL');
CREATE TYPE overlap_action_enum AS ENUM ('ALLOW', 'SKIP', 'CANCEL_PREV', 'PARALLEL');
CREATE TYPE failure_action_enum AS ENUM ('RUN_NEW', 'SKIP', 'RETRY');
CREATE TYPE task_status_enum AS ENUM ('ENABLED', 'DISABLED');
CREATE TYPE run_status_enum AS ENUM (
    'SCHEDULED', 'RUNNING', 'SUCCESS', 'FAILED', 'TIMEOUT', 'RETRYING',
    'CALLBACK_PENDING', 'CALLBACK_SUCCESS', 'CALLBACK_FAILED', 'FAILED_TIMEOUT',
    'CANCELED', 'SKIPPED', 'FAILURE_SKIP', 'CONCURRENT_SKIP', 'OVERLAP_SKIP'
);
CREATE TYPE callback_status_enum AS ENUM ('RECEIVED', 'IGNORED');

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  description VARCHAR(512) DEFAULT '',
  cron_expr VARCHAR(64) NOT NULL,
  timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
  exec_type exec_type_enum NOT NULL DEFAULT 'SYNC',
  http_method VARCHAR(8) NOT NULL DEFAULT 'GET',
  target_service VARCHAR(64) NOT NULL DEFAULT 'artemis',
  target_path VARCHAR(512) NOT NULL DEFAULT '',
  headers_json JSONB,
  body_template TEXT,
  retry_policy_json JSONB,
  max_concurrency INTEGER NOT NULL DEFAULT 1,
  concurrency_policy concurrency_policy_enum NOT NULL DEFAULT 'QUEUE',
  callback_method VARCHAR(8) DEFAULT 'POST',
  callback_timeout_sec INTEGER DEFAULT 300,
  overlap_action overlap_action_enum NOT NULL DEFAULT 'ALLOW',
  failure_action failure_action_enum NOT NULL DEFAULT 'RUN_NEW',
  status task_status_enum NOT NULL DEFAULT 'ENABLED',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted SMALLINT NOT NULL DEFAULT 0
);

-- Create task_runs table
CREATE TABLE IF NOT EXISTS task_runs (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT NOT NULL,
  scheduled_time TIMESTAMP NOT NULL,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  status run_status_enum NOT NULL DEFAULT 'SCHEDULED',
  attempt INTEGER NOT NULL DEFAULT 1,
  target_service VARCHAR(64) NOT NULL DEFAULT 'artemis',
  target_path VARCHAR(512) NOT NULL DEFAULT '',
  method VARCHAR(16) NOT NULL DEFAULT 'POST',
  exec_type VARCHAR(16) NOT NULL DEFAULT 'SYNC',
  request_headers JSONB,
  request_body TEXT,
  response_code INTEGER,
  response_body TEXT,
  error_message VARCHAR(1024),
  next_retry_time TIMESTAMP,
  callback_token CHAR(32),
  callback_deadline TIMESTAMP,
  trace_id VARCHAR(64),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uniq_task_schedule UNIQUE (task_id, scheduled_time),
  CONSTRAINT fk_task_runs_task FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Create async_callbacks table
CREATE TABLE IF NOT EXISTS async_callbacks (
  id BIGSERIAL PRIMARY KEY,
  task_run_id BIGINT NOT NULL,
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  headers_json JSONB,
  body TEXT,
  status callback_status_enum NOT NULL DEFAULT 'RECEIVED',
  CONSTRAINT fk_callbacks_run FOREIGN KEY (task_run_id) REFERENCES task_runs(id)
);

-- Create scheduler_locks table
CREATE TABLE IF NOT EXISTS scheduler_locks (
  lock_name VARCHAR(64) PRIMARY KEY,
  owner_id VARCHAR(128) NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_task_time ON task_runs(task_id, scheduled_time);
CREATE INDEX idx_status ON task_runs(status);
CREATE INDEX idx_next_retry ON task_runs(next_retry_time);
CREATE INDEX idx_callback_token ON task_runs(callback_token);
CREATE INDEX idx_task_run ON async_callbacks(task_run_id);

-- Create a function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_runs_updated_at BEFORE UPDATE ON task_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scheduler_locks_updated_at BEFORE UPDATE ON scheduler_locks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();