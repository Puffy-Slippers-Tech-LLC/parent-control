### Task 17 — Implement and test broker-owned natural grant-expiry reconciliation

- Complexity: very high. This is a privileged transactional scheduler with
  startup, timer, race, and rollback behavior.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: close the documented implementation gap before release E2E tests
  rely on natural expiry.
- Work:
  1. Implement the broker-owned design already specified in
     `System-Design.md`: read ActiveExtension at startup, schedule the verified
     expiry, re-read authoritative state at the deadline, restore the canonical
     hard-and-soft filter only when no grant remains, and activate fapolicyd
     transactionally.
  2. Reschedule safely after approval, extension changes, revocation, parent-
     control changes, clock changes, broker restart, and child removal.
  3. Serialize expiry with approval and revocation so stale timers cannot undo a
     newer grant or policy.
  4. Add PII-safe logs for schedule, cancellation, wake, stale deadline, filter
     restore, accepted outcome, backend failure, and rollback failure.
  5. Add deterministic fake-clock unit tests, private-D-Bus component tests, and
     installed-system tests with real short grants.
  6. Prove hard blocks never relax, soft blocks restore on natural expiry, and
     unrelated children remain unchanged.
  7. Update `System-Design.md` to remove the implementation-gap statement and
     describe the completed lifecycle.
  8. Verify the existing package-activation classification for changed broker
     files and update activation tests in the same change.
  9. Update all natural-expiry requirement mappings. Do not mark the behavior
     skipped or expected-failing.
- Verification:
  - Run focused scheduler race and rollback tests repeatedly.
  - Run the installed short-grant expiry scenario.
  - Run `make check-component`, `make check-system`, `make check`, and
    `git diff --check`.
- Completion criteria: natural expiry restores canonical application enforcement
  after startup and at runtime, with transactional failure behavior and no stale-
  timer race.

