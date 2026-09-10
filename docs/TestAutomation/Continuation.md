# Current implementation continuation

Updated: 2026-09-10. The [master checklist](Test-Automation.md#unfinished-tasks)
owns task order and completion.

- **Current: Task 20 — implement the VT6 prompt needle and one-shot input route**;
  [active handoff](Task-20.md#task-20-continuation--2026-09-08),
  [local session-gate evidence](Evidence/20-VT6-Session-Gate-20260910.md),
  [passing prompt evidence](Evidence/20-VT6-Prompt-Qualification-20260910.md),
  [owning VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal).
  The fixed `vt6-session` observer now passes local selected-session, active-VT,
  transport/refusal and shared graphical/serial consumer checks. It is not yet
  wired to an authenticated worker and does not prove shell readiness or
  continuity from the earlier login recipient. Reuse it with the existing
  credential/private capture helpers and the reviewed native 1024×768 pixels.
  Implement the exact matcher and one-shot VNC worker/controller gates; verify
  wrong-account/stale-screen/missing-prompt refusals, boot/recipient continuity,
  capture sealing and no retry before the smallest guarded authenticated
  success/failure qualification after isolated safety checks. Empty no-echo
  pixels cannot prove no invisible input. Keep inputs unchanged through finalization.
  Do not repeat prompt-only collection or maintenance without new evidence.
  Sudo/notice pixels and full install/reboot/startup remain unfinished.
- **Selection rechecked:** Task 20 earliest ready; no bypass.
  [15A's later work](Task-15.md#task-15a-continuation--2026-09-08) stays preserved.
- **All-task VM clearance persists** under the
  [shared rule](Implementation-Workflow.md#vm-availability-for-all-tasks).
  All commands started this session exited: 1,470 focused tests passed;
  `make check` passed 6,631 unit/contract and 58 private-D-Bus component tests.
  No VM operation, lease, worker or screenshot export was created; no recovery
  remains. Prior VM cleanup and the original failed prompt attempt remain in
  their evidence. Task 20 is unaccepted; no live session qualification is claimed.
- Settings: **`gpt-6-astra` / `high`**.
  Reason: the session observer and shared consumers pass locally, but reviewed-screen
  secret authorization, recipient/input continuity and capture sealing across
  the new VNC route remain unresolved security/correctness boundaries.
