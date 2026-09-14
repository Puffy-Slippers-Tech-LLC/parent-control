# Task 15 — Separate installed enforcement work

**Scope — 2026-09-14:** unfinished installed enforcement engineering is deferred
outside the prioritized customer E2E queue. Existing tests, assertions and
qualified evidence remain unchanged. Customer launch and user-isolation
scenarios proceed in [Task 25](Task-25.md) using visible results; they do not
depend on acceptance of 15A/15B.

The unresolved production policy-acknowledgement protocol and all retained
15A work are in [Policy-Acknowledgement.md](Policy-Acknowledgement.md). It
requires a separate explicit design/repair decision and must not return as an
implicit scenario prerequisite.

## Implementation slices

There is no automatic implementation slice for this deferred engineering work.
Do not select it when an E2E journey lacks an internal witness. A demonstrated
customer failure remains an explicit blocker in the affected scenario's handoff.

## Task 15A

- Title: Deferred installed catalog and launch-enforcement matrix.
- Status: Unaccepted separate engineering; outside the active launcher queue.
- Retained scope: native/Snap/Flatpak positive, negative, matching and cross-user
  installed cases; existing fixtures, tests and results stay intact.
- Design separation: policy acknowledgement is owned by the
  [separate handoff](Policy-Acknowledgement.md#unresolved-product-contract-and-blockers),
  not an additional completion criterion silently attached to this matrix.
- Customer ownership: [25A](Task-25.md#task-25a) tests launch outcomes through
  actual customer routes without rule, daemon or execution-probe assertions.

## Task 15A continuation — 2026-09-08

Historical link retained for existing references. The former continuation and
attempts are preserved in
[the engineering record](Policy-Acknowledgement.md#task-15a-continuation--2026-09-08).
The current [Continuation.md](Continuation.md) selects customer work.
No old probe next action or model recommendation is reactivated by this link.

## Task 15B

- Title: Deferred process-confinement and rollback qualification.
- Status: Unaccepted separate engineering; outside the active launcher queue.
- Retained scope: exact process ownership, kernel identities, rollback/readback,
  induced reload failure and partial termination; preserve existing regressions
  and the [original specification](Policy-Acknowledgement.md#task-15b).
- Customer ownership: [25B](Task-25.md#task-25b) observes the selected child's
  application windows and another user's continued use. It makes no internal
  atomicity, PID or rollback proof claim.
