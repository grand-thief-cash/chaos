-- Migration: convert all TIMESTAMP (without time zone) columns to TIMESTAMPTZ
--
-- Background: the cronjob container runs with TZ=Asia/Shanghai while the postgres
-- session timezone is Etc/UTC. Time columns were declared TIMESTAMP WITHOUT TIME ZONE,
-- so Go time.Now()/scheduler fire-time (Beijing local) got stored as bare wall-clock
-- with the +08 offset stripped, and read back as UTC -- shifting every instant by 8h.
--
-- This broke the scheduler dedup (existing[ft.Unix()] collided a 20:00 Beijing fire
-- with a 12:00 Beijing run whose stored "12:00" read back as 12:00 UTC = 20:00 Beijing),
-- silently skipping fires. It also made manually-triggered runs show an 8h gap between
-- scheduled_time (written via time.Now().UTC()) and start_time (written via time.Now()).
--
-- Fix: store real instants. Existing wall-clock values are reinterpreted as Asia/Shanghai
-- (the wall-clock the Go process actually produced), except task_runs.scheduled_time for
-- manually-triggered rows, which were written as UTC wall-clock via time.Now().UTC().
-- Manual rows are identified by start_time - scheduled_time ≈ 8h (auto rows are ≈1s).

-- 1. tasks: created_at / updated_at written by Go time.Now() (Beijing wall-clock)
ALTER TABLE tasks ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE tasks ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'Asia/Shanghai';

-- 2. task_runs: scheduled_time is mixed (auto=Beijing wall-clock, manual=UTC wall-clock)
ALTER TABLE task_runs ALTER COLUMN scheduled_time TYPE timestamptz USING (
    CASE
        WHEN start_time IS NOT NULL AND (start_time - scheduled_time) > INTERVAL '1 minute'
        THEN scheduled_time AT TIME ZONE 'UTC'              -- manual trigger: written as UTC wall-clock
        ELSE scheduled_time AT TIME ZONE 'Asia/Shanghai'    -- auto fire: written as Beijing wall-clock
    END
);
ALTER TABLE task_runs ALTER COLUMN start_time TYPE timestamptz USING start_time AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE task_runs ALTER COLUMN end_time TYPE timestamptz USING end_time AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE task_runs ALTER COLUMN next_retry_time TYPE timestamptz USING next_retry_time AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE task_runs ALTER COLUMN callback_deadline TYPE timestamptz USING callback_deadline AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE task_runs ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE task_runs ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'Asia/Shanghai';

-- 3. async_callbacks: received_at written by Go time.Now() (Beijing wall-clock)
ALTER TABLE async_callbacks ALTER COLUMN received_at TYPE timestamptz USING received_at AT TIME ZONE 'Asia/Shanghai';

-- 4. scheduler_locks: expires_at / updated_at written by Go time.Now() (Beijing wall-clock)
ALTER TABLE scheduler_locks ALTER COLUMN expires_at TYPE timestamptz USING expires_at AT TIME ZONE 'Asia/Shanghai';
ALTER TABLE scheduler_locks ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'Asia/Shanghai';

-- 5. updated_at trigger: CURRENT_TIMESTAMP returns timestamptz, compatible with the new
--    column type. Recreate the function body to keep it in sync (no behavior change).
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
