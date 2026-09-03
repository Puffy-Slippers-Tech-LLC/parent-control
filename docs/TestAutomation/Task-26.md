### Task 26 — Automate failure, concurrency, persistence, and recovery scenarios

- Complexity: very high. Failures must occur at controlled real boundaries
  without adding production backdoors.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove fail-closed and rollback guarantees across restarts and user
  interactions.
- Work:
  1. Exercise invalid and unauthorized calls, Polkit denial and cancellation,
     requester disconnect, account and preference changes during authentication,
     usage-query failure, broker restart, authentication-agent failure,
     fapolicyd reload failure, and process-termination failure.
  2. Use disposable-guest service and process controls at public OS boundaries.
     Do not add a hidden failure-injection method to production.
  3. Verify each reversible failure restores the complete prior state and reports
     rollback failure distinctly when read-back cannot be verified.
  4. Verify irreversible partial process termination keeps strict blocks and old
     time while leaving other users untouched.
  5. Submit concurrent and rapid repeat requests and revocations and prove single-
     flight serialization, exactly-once grant changes, and correct rate-interval
     consumption.
  6. Restart Parent, request surfaces, broker, affected user sessions, package
     services, and the whole VM; verify preferences, remembered choices, grants,
     extension publication, and enforcement at each documented boundary.
  7. Verify all displayed failures are actionable and reveal no internal path,
     service name, account PII, or backend detail.
  8. Update failure, concurrency, persistence, and recovery requirement mappings.
- Verification:
  - Run each destructive failure from its own fresh overlay.
  - Compare before/after authoritative state snapshots and review redacted logs.
  - Run `make check-e2e` for these scenarios, `make check`, and
    `git diff --check`.
- Completion criteria: every specified failure class has a deterministic
  fail-closed scenario and all persistence boundaries are exercised.

