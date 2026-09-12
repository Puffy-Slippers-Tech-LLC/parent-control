# Current implementation continuation

Updated: 2026-09-11. The [master checklist](Test-Automation.md#unfinished-tasks)
owns task order and completion.

- Next: [Task 15A](Task-15.md#task-15a-continuation--2026-09-08).
  Establish independently owned, bounded bus-client creation/closure so delayed
  dispatch cannot pin a reference on the broker's long-lived connection; then
  resolve original-job binding and qualify success/failure/cleanup.
- The operator prioritized Tasks 15–18, 21–27 and 28A before Task 20, especially
  installed-app behavior and families' everyday journeys. Select in
  master-checklist order with actual dependencies; 28B/C remain after Task 20.
  Verified installation is prerequisite setup. Qualify any missing shared
  helper with the first affected consumer and publish evidence for reuse;
  this does not require full Task 20 acceptance or waive its coverage.
  This supersedes the Task 20-first scope.
- Preserve [Task 20 recovery R1](Task-20.md#task-20-continuation--2026-09-08)
  for resumption in checklist order. Its ledger remains 0 charged hours and
  0 new attempts, next checkpoint 4 hours, decision hold none. Its recovery
  checkpoints apply when Task 20 resumes or an earlier consumer brings forward
  R1 recovery; charge only that recovery portion, not unrelated consumer work.
- All-task VM clearance persists. Stable live inputs remain required; historical
  one-slice overrides stay consumed. No launcher or VM was started by this update.
- Settings: **`gpt-6-astra` / `high`**.
  Reason: dedicated client cancellation/closure and original-job binding still
  require ownership/concurrency reasoning; use Sol high once settled.
