# Current implementation continuation

Updated: 2026-09-11. The [master checklist](Test-Automation.md#unfinished-tasks)
owns task order and completion.

- Next: [Task 15A acknowledgement](Task-15.md#task-15a-continuation--2026-09-08).
  Implement and locally prove a narrowly scoped systemd transient probe operation
  through the existing Gio transport: execution/start timeout, lost create reply,
  collision/replacement, evidence retention and owned cleanup. The
  [kernel audit](Evidence/15A-Kernel-Witness-Audit-20260911.md) rules out nonce
  denials and early markers; full receipt and rollback/removal semantics remain
  unimplemented. Do not use subprocess timeout as a bound on initial exec.
- Earlier [Task 20 deferral](Task-20.md#task-20-continuation--2026-09-08): retained
  source-preservation failures and no writer-completion/pause evidence. Return
  first when completion or a coordinated window covers capture through cleanup;
  then run fresh guarded VT6 qualification. No unchanged stability experiment.
- The one-slice override is consumed. All-task VM clearance persists. Live
  qualification requires stable inputs; no new VM approval or manual-review hold.
- Settings: **`gpt-6-astra` / `high`**.
  Reason: the source audit identifies a supported systemd execution candidate;
  lost-reply ownership, terminal evidence lifetime and timeout cleanup remain
  unresolved security/concurrency boundaries requiring Astra high.
