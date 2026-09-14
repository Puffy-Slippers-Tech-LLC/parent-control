# Current implementation continuation

Updated: 2026-09-14. The [master checklist](Test-Automation.md#unfinished-tasks)
prioritizes customer E2E generally, followed by mechanical package qualification.
This document supersedes the former Task 15A probe continuation.

- Next: [Task 21A](Task-21.md#current-handoff--2026-09-14), first complete
  `E2E-003/existing-and-new`: parent logs in, opens Parent, selects an existing
  child and observes discovery of a new eligible fixture account without
  restarting Parent. Observe the UI; no catalog/broker product probes.
- Reuse verified package/account setup and accepted graphical input. Reconcile
  this pending declaration and the minimum shared evidence validator so customer
  assertions require no backend product witnesses. Keep VM, provenance, secret
  input and cleanup safeguards. Do not qualify all internals or other task matrices.
- The implementation agent must wire this scenario's executable, mark its
  inventory entry `ready` when runnable, verify `tools/run-tests e2e --list`
  discovers it, and obtain a complete passing run before claiming completion.
  `make test-all` includes ready entries automatically; registration requires
  no manual operator step and must not wait for a later task.
- Customer progress baseline: 0 completed; one harness smoke ready; 156 legacy
  variants pending before explicit scope reconciliation. Current selected finish
  line: one complete Parent discovery journey. Consecutive implementation slices without
  a completed customer variant since this scope reset: 0. No implementation or
  runtime acceptance occurred in this documentation session.
- Preserve demonstrated failures and separate product blockers. The
  [policy-acknowledgement work](Policy-Acknowledgement.md) is deferred, not a
  scenario dependency or automatic fallback.
- Task 20's [R1 ledger](Task-20.md#task-20-continuation--2026-09-08) remains
  0 charged hours / 0 new attempts, next checkpoint 4 hours, no decision hold.
  Charge only actual R1 recovery; mechanical installation checks remain required.
- No implementation, runtime tests or VM operations ran in this documentation session.
  Reconcile actual runner/lease ownership before execution; historical cleanup
  is not current VM-state evidence. All-task guarded VM authorization persists.
- Settings: **`gpt-5.6-sol` / `high`**.
  Reason: implement one bounded visible Parent journey using accepted tools;
  internal policy design is outside this slice.
