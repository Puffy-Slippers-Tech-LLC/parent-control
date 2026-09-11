# Current implementation continuation

Updated: 2026-09-10. The [master checklist](Test-Automation.md#unfinished-tasks)
owns task order and completion.

- **Current: Task 20 — prove authenticated VT6 shell readiness and lineage**;
  [active handoff](Task-20.md#task-20-continuation--2026-09-08),
  [recipient-gate evidence](Evidence/20-VT6-Recipient-Gate-20260910.md),
  [owning protocol and limitations](../../tests/e2e/README.md#visible-vt6-installation-terminal).
  The observer now pins boot/process identity through an ordered single-use
  getty/password/recheck sequence. Reuse it with `vt6-session` and the established
  direct-login-child observer semantics to prove authenticated shell lineage
  and command-input readiness. Session activity or a Bash executable alone is
  insufficient; login forks a shell with a new session ID. The worker remains
  unselected by `smoke.pm`. Bind current worker, fresh private capture,
  provenance-bound reference, unchanged boot and exact pixel comparison to
  durable one-use authorization before enabling dispatch. Qualify the smallest
  guarded authenticated success/refusal after isolated safety checks once all
  receipts have executable proofs. Keep inputs unchanged through finalization.
  Do not repeat prompt-only collection or infer invisible input from blank pixels.
  Sudo/notice pixels and full install/reboot/startup remain unfinished.
- **Selection rechecked:** Task 20 earliest ready; no bypass.
  [15A's later work](Task-15.md#task-15a-continuation--2026-09-08) stays preserved.
- **All-task VM clearance persists** under the
  [shared rule](Implementation-Workflow.md#vm-availability-for-all-tasks).
  Missing controller proofs limit implementation readiness. All started commands
  exited: 1,561 focused tests and `make check` passed (6,973 unit/contract and
  58 private-D-Bus component tests). No current test failure, VM operation,
  lease, worker, callback or screenshot export; no cleanup or recovery remains.
  Historical failures stay retained in the handoff's evidence. Task 20 is
  unaccepted; local observer verification does not qualify live authentication.
- Settings: **`gpt-6-astra` / `high`**.
  Reason: recipient pinning and replay refusal now pass locally, but proving
  shell readiness/lineage and binding fresh captures to durable authorization
  remain unresolved security/correctness boundaries before credential dispatch.
