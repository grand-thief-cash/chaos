# Cronjob Refactoring Plan (Revised)

## Background
Based on the code review and user feedback, we need to refactor the `cronjob` project to improve context propagation, leverage the `http_client` component, and support multi-tenant downstream services. The refactoring will focus on making `TaskRun` the self-sufficient message carrier and removing redundant configurations.

## Objectives
1.  **TaskRun as Single Source of Truth:** `TaskRun` should carry all necessary information for execution (Context, Snapshot), serving as a complete message payload.
2.  **Eliminate Redundant Configs:** Remove `TimeoutSeconds` from `Task` and rely on `http_client` component configurations.
3.  **Optimize HTTP Client Usage:** Use `http_client` for base URL management and support multiple downstream services.
4.  **Data Consistency:** `TaskRun` should snapshot the request data *before* execution, and the executor should use this snapshot.

## Phase 1: Enhance `TaskRun` Model & Snapshotting

### 1.1 Update `TaskRun` Model
Modify `internal/model/run.go` to include fields that make the run self-sufficient (snapshotting the Task configuration at time of creation).
*   Add `TargetService` (string)
*   Add `TargetPath` (string)
*   Add `Method` (string)
*   *Note: `RequestHeaders` and `RequestBody` already exist and should be populated at creation time.*

### 1.2 Update `Task` Model
Modify `internal/model/task.go`:
*   Remove `TimeoutSeconds` (Use `http_client` config).
*   Remove `TargetURL` (Replace with `TargetService` + `TargetPath`).
*   Add `TargetService` (default "artemis").
*   Add `TargetPath`.

### 1.3 Snapshotting Logic
Update the `TaskService` or Scheduler logic that creates `TaskRun`:
*   When creating a `TaskRun`, resolve `BodyTemplate` and `HeadersJSON` immediately.
*   Populate `TaskRun.RequestBody` and `TaskRun.RequestHeaders` with the resolved content.
*   Populate `TaskRun.TargetService`, `TargetPath`, `Method` from the `Task`.
*   *Outcome:* The `TaskRun` object now contains everything needed to execute.

## Phase 2: Refactor Executor to use `TaskRun`

### 2.1 Worker Channel
*   Keep `chan *model.TaskRun` as the channel type.
*   The `Executor.Enqueue(run)` should receive the fully populated `TaskRun` (with snapshots).

### 2.2 Execution Logic (`executor.go`)
*   **Remove Task Lookup:** Remove `e.TaskSvc.Get(ctx, run.TaskID)` from `execute`. Reliability is improved as we don't depend on `Task` existing or being unchanged.
*   **Context Rehydration:** Ensure `execute` re-creates the `context.Context` from `TaskRun.TraceID` effectively.
*   **Request Construction:** Build the `http.Request` using ONLY fields from `TaskRun` (`TargetService`, `TargetPath`, `Method`, `RequestBody`, `RequestHeaders`).

## Phase 3: Enhance HTTP Client & Multi-Tenancy

### 3.1 HTTP Client Integration
*   In `Executor.execute` (or `doHTTP`), use `run.TargetService` to fetch the correct client: `cli, err := e.HTTPCli.Client(run.TargetService)`.
*   Use the client's configured timeout (removing the need for `Task.TimeoutSeconds`).
*   Call `cli.Do(...)` passing the relative `run.TargetPath` and `run.RequestHeaders`.

### 3.2 Dynamic Client Config
*   Update `config.yaml` to allow defining arbitrary clients under `http_clients`.
*   (Optional) Provide an endpoint to list available clients for the UI.

## Phase 4: Data Consistency Implementation

### 4.1 Persistence
*   Since `TaskRun` is pre-populated with "Planned" request data, the `persistOutboundSnapshot` logic might change to "Update only if changed" or simply "Record Response".
*   If the Executor modifies headers (e.g. adding Trace Context), update `TaskRun.RequestHeaders` to reflect the *actual* wire data.

## Execution Steps summary
1.  **Model Updates:** Modify `Task` and `TaskRun` structs and DB migrations.
2.  **Creation Logic:** Move template resolution and snapshotting to the `CreateRun` phase.
3.  **Executor Refactor:** Strip out `Task` dependencies and use `http_client` strictly.


