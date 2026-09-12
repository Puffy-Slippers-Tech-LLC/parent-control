# Current implementation continuation

Updated: 2026-09-11. The [master checklist](Test-Automation.md#unfinished-tasks)
owns task order and completion.

- Next: [Task 15A](Task-15.md#task-15a-continuation--2026-09-08).
  Integrate the locally tested broker channel under the
  [pre-exec admission contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness):
  authenticate captured manager, returned job, exact unit/command, MainPID and
  stable invocation before supplying the channel binding; retain generation
  directory/witness ownership and compare terminal evidence with the admitted
  invocation. Reuse [ProbeChannel and its safety/native checks](Evidence/15A-Probe-Broker-Channel-20260911.md)
  plus `ExecutionProbe`'s retained lifecycle. Test replacement and terminal
  failure without replay or lost unit/client ownership, then qualify the guarded
  guest. Keep the boot canary and `identity-unproven` refusal; local channel
  outcomes are not installed or generation-receipt acceptance.
  Task 15A remains the earliest ready unchecked entry; none was bypassed.
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
  one-slice overrides stay consumed. Final native checks passed 66 tests after
  isolated safety prerequisites; `make check` passed 7589 unit and 134 component
  tests plus source validation. Native children joined, sockets/pipes/directory
  descriptors closed and temporary fixtures reconciled/removed; all commands
  exited. No VM/systemd
  attempt or Task 20 recovery work ran. No cleanup or denial remains outstanding.
- Settings: **`gpt-6-astra` / `high`**.
  Reason: the channel's single-use admission, native exec/refusal and socket
  cleanup are proven locally; manager/invocation authentication, replacement
  races and retained lifecycle ownership still require Astra before settled
  implementation is appropriate.
