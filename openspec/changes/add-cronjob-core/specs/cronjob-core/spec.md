## ADDED Requirements

### Requirement: Cronjob registration

The gateway SHALL provide a cronjob manager that registers cronjobs by unique name before or after the manager starts.

#### Scenario: Register a cronjob
- **WHEN** a cronjob is registered with a name that is not already registered
- **THEN** the manager stores the cronjob for lifecycle control and status reporting

#### Scenario: Reject duplicate cronjob names
- **WHEN** a cronjob is registered with a name that is already registered
- **THEN** the manager rejects the registration

### Requirement: Cronjob lifecycle

The gateway SHALL start and stop enabled cronjob loops from the FastAPI process lifecycle.

#### Scenario: Start enabled cronjobs
- **WHEN** the manager starts with enabled cronjobs registered
- **THEN** each enabled cronjob has one background loop

#### Scenario: Ignore disabled cronjobs
- **WHEN** the manager starts with a disabled cronjob registered
- **THEN** the disabled cronjob does not start a background loop

#### Scenario: Stop cronjobs cleanly
- **WHEN** the manager stops
- **THEN** it cancels running cronjob loop tasks
- **AND** it awaits cancelled tasks without leaving unhandled task exceptions

### Requirement: Scheduled cronjob execution

The gateway SHALL run each enabled cronjob repeatedly according to its configured interval.

#### Scenario: Run cronjob on interval
- **WHEN** an enabled cronjob loop is running
- **THEN** the manager sleeps for the cronjob interval
- **AND** runs the cronjob once after each elapsed interval until stopped

#### Scenario: Run cronjob on start
- **WHEN** an enabled cronjob has `run_on_start` set to true
- **THEN** the manager runs the cronjob once before waiting for the first interval

### Requirement: On-demand cronjob execution

The gateway SHALL allow callers to trigger a registered cronjob once by name.

#### Scenario: Run registered cronjob on demand
- **WHEN** a caller requests one execution for a registered enabled cronjob
- **THEN** the manager runs that cronjob once using the same execution guard as scheduled runs

#### Scenario: Reject unknown cronjob on demand
- **WHEN** a caller requests one execution for an unknown cronjob name
- **THEN** the manager rejects the request

### Requirement: Non-overlapping cronjob runs

The gateway SHALL prevent overlapping executions of the same cronjob.

#### Scenario: Skip tick while cronjob is running
- **WHEN** a scheduled tick occurs while the same cronjob is still running
- **THEN** the manager skips that tick
- **AND** the existing cronjob run continues

#### Scenario: Skip on-demand run while cronjob is running
- **WHEN** a caller requests an on-demand run while the same cronjob is already running
- **THEN** the manager skips the new run
- **AND** the existing cronjob run continues

### Requirement: Cronjob failure isolation

The gateway SHALL isolate cronjob failures so one failed cronjob does not stop the manager or other cronjobs.

#### Scenario: Cronjob raises an exception
- **WHEN** a cronjob execution raises an exception
- **THEN** the manager logs the failure
- **AND** records failure status for that cronjob
- **AND** keeps other cronjob loops running

### Requirement: Cronjob status

The gateway SHALL expose in-memory status for each registered cronjob.

#### Scenario: Status includes runtime fields
- **WHEN** a caller requests cronjob status
- **THEN** the manager returns one status entry per registered cronjob
- **AND** each entry includes name, enabled, running, last started time, last finished time, last succeeded time, last failed time, last error, run count, and failure count

#### Scenario: Successful run updates status
- **WHEN** a cronjob execution succeeds
- **THEN** the manager records finish and success timestamps
- **AND** increments the run count

#### Scenario: Failed run updates status
- **WHEN** a cronjob execution fails
- **THEN** the manager records finish and failure timestamps
- **AND** stores the latest error text
- **AND** increments the run count and failure count

### Requirement: Per-process execution semantics

The gateway SHALL treat cronjob execution as per-process behavior.

#### Scenario: Multiple gateway processes run independently
- **WHEN** multiple gateway processes or workers each start their own cronjob manager
- **THEN** each process manages its own cronjob loops independently
- **AND** the core does not guarantee exactly-once execution across processes
