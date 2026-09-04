# Task 17 — Expired-grant reconciliation at session entry

The current specification (`ONPC-CORE-APPS-011`,
`ONPC-COMP-CHILD-005`, and `ONPC-COMP-BROKER-009`) and
`System-Design.md` require reconciliation at new-session entry and unlock.
`Broker.prepare_own_session` already implements this path. Expiry locks the
desktop without immediately closing apps; the broker re-reads the grant under
the transaction lock before restoring policy and terminating apps at session
entry. A current replacement grant makes preparation a no-op. The former
timer-scheduler task described obsolete behavior and must not be implemented.

## Task 17A

- Title: Complete session-entry transaction and race regressions.
- Depends on: Task 16B.
- Complexity: very high. A stale expiry observation must never override a
  replacement grant or weaken rollback and process ownership guarantees.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Review the existing broker method, D-Bus worker, and child startup/unlock
     calls against the current specification. Reuse working behavior; fix only
     demonstrated gaps, with PII-safe stage/outcome/error logs.
  2. Add deterministic unit and private-D-Bus component cases for expired,
     cleared, malformed, unreadable, and active replacement grants. Read the
     authoritative grant after acquiring the shared transaction lock.
  3. Cover contention with policy save, approval, revocation, and parent-control
     changes; ensure a stale child observation cannot restore an old policy.
     Cover changed/removed accounts and broker restart without inventing a timer.
  4. Verify canonical hard/soft targets and patterns, termination preflight,
     filter/fapolicyd verification before termination, rollback before side
     effects, and strict-policy retention after partial termination.
  5. Verify child calls at extension startup and unlock, with no child-owned
     grant decisions or process signalling. Run shared form regressions in
     both modes if those files change.
  6. Update architecture documentation only where actual behavior changes.
     Classify changed packaged files and update activation tests in the same
     change; migrate saved data first if an incompatible change is necessary.
  7. Map proven unit/component behavior; leave installed and graphical evidence
     pending for 17B and Task 22.
- Verification:
  - Run focused deterministic transaction, race, and rollback tests.
  - Run cleanup-safety regressions before host-integrated component tests.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: the existing session-entry contract has executable race
  and failure coverage, and any demonstrated implementation gaps are fixed.

## Task 17B

- Title: Prove expired and replacement grants on the installed system.
- Depends on: Task 17A.
- Complexity: high. Reuse the established transaction and guest controls to
  verify real AccountsService, fapolicyd, and process results.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Use real short grants and identity-recorded apps. Prove expiry alone does
     not terminate retained-session applications.
  2. Call `PrepareOwnSession` as the actual child after expiry; verify complete
     policy activation precedes child-only blocked-app termination.
  3. Approve a replacement grant between expiry and preparation. For a grant
     allowing soft apps, prove the hard-only filter and all running apps remain.
     For a grant keeping soft blocks, prove preparation preserves the completed
     approval transaction instead of repeating it.
  4. Verify cleared grants, broker restart, authoritative read failure, and
     controlled transaction contention using 17A's contract and public guest
     boundaries. Observe a second child and unrelated users in every case.
  5. Update installed reconciliation mappings; keep graphical entry/unlock
     assertions assigned to Task 22.
- Verification:
  - Run fixture cleanup-safety regressions in isolation before live cases.
  - Run installed short-grant/replacement-grant cases in fresh testbeds and
    record filters, process identities, grants, and redacted logs.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: installed evidence proves expired-grant reconciliation
  and replacement-grant precedence without adding deadline-driven termination.
