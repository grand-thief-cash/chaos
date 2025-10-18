-- Migration: initial schema

CREATE TABLE IF NOT EXISTS tasks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL UNIQUE,
  description VARCHAR(512) DEFAULT '',
  cron_expr VARCHAR(64) NOT NULL,
  timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
  exec_type ENUM('SYNC','ASYNC') NOT NULL DEFAULT 'SYNC',
  http_method VARCHAR(8) NOT NULL DEFAULT 'GET',
  target_url VARCHAR(512) NOT NULL,
  headers_json JSON NULL,
  body_template TEXT NULL,
  timeout_seconds INT NOT NULL DEFAULT 10,
  retry_policy_json JSON NULL,
  max_concurrency INT NOT NULL DEFAULT 1,
  concurrency_policy ENUM('QUEUE','SKIP','PARALLEL') NOT NULL DEFAULT 'QUEUE',
  misfire_policy ENUM('FIRE_NOW','SKIP','CATCH_UP_LIMITED') NOT NULL DEFAULT 'FIRE_NOW',
  catchup_limit INT NOT NULL DEFAULT 0,
  callback_method VARCHAR(8) DEFAULT 'POST',
  callback_timeout_sec INT DEFAULT 300,
  overlap_action ENUM('ALLOW','SKIP','CANCEL_PREV','PARALLEL') NOT NULL DEFAULT 'ALLOW',
  failure_action ENUM('RUN_NEW','SKIP','RETRY') NOT NULL DEFAULT 'RUN_NEW',
  status ENUM('ENABLED','DISABLED') NOT NULL DEFAULT 'ENABLED',
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS task_runs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  scheduled_time DATETIME NOT NULL,
  start_time DATETIME NULL,
  end_time DATETIME NULL,
  status ENUM('SCHEDULED','RUNNING','SUCCESS','FAILED','TIMEOUT','RETRYING','CALLBACK_PENDING','CALLBACK_SUCCESS','FAILED_TIMEOUT','CANCELED','SKIPPED') NOT NULL DEFAULT 'SCHEDULED',
  attempt INT NOT NULL DEFAULT 1,
  request_headers JSON NULL,
  request_body MEDIUMTEXT NULL,
  response_code INT NULL,
  response_body MEDIUMTEXT NULL,
  error_message VARCHAR(1024) NULL,
  next_retry_time DATETIME NULL,
  callback_token CHAR(32) NULL,
  callback_deadline DATETIME NULL,
  trace_id VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_task_schedule(task_id, scheduled_time),
  KEY idx_task_time(task_id, scheduled_time),
  KEY idx_status(status),
  KEY idx_next_retry(next_retry_time),
  KEY idx_callback_token(callback_token),
  CONSTRAINT fk_task_runs_task FOREIGN KEY (task_id) REFERENCES tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS async_callbacks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_run_id BIGINT NOT NULL,
  received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  headers_json JSON NULL,
  body MEDIUMTEXT NULL,
  status ENUM('RECEIVED','IGNORED') NOT NULL DEFAULT 'RECEIVED',
  KEY idx_task_run(task_run_id),
  CONSTRAINT fk_callbacks_run FOREIGN KEY (task_run_id) REFERENCES task_runs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Optional lock table for future distributed scheduling
CREATE TABLE IF NOT EXISTS scheduler_locks (
  lock_name VARCHAR(64) PRIMARY KEY,
  owner_id VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
