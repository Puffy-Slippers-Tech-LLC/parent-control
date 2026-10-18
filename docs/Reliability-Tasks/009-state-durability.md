# 009 — Durable request-state failure and retry

Acceptance: host

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Estimate: 15–30 minutes.

## Session boundary

Deliver non-authoritative selector fallback and subsequent normal persistence.
009a supplies authoritative preference write/replace/flush failures. Agent-locale
retry, supersession and late-reply ordering moved to 008c/008a, inherited through
008. Together these preserve original 009's obligations with one owner each.

## Purpose and route

Required tasks: 008, 009a.
Read the [master](../Reliability-Plan.md),
[state durability contract](../SystemDesign/State.md),
[frontend state ownership](../SystemDesign/Frontends.md),
the kiosk `selection_store.py`, its callers and complete relevant host tests.

Extend canonical selector/request-state host tests, including the relevant
`test_request_time_estimate.py` callers; inspect exact ownership before adding a
case. Use launcher-configured private filesystem fixtures and real store logic.
No host disk exhaustion, permission changes to shared paths or additional
database is needed.

## Finite failures and expected results

For non-authoritative selector files, pair malformed JSON and unwritable storage
with the documented in-memory fallback, reviewed failure stage and later normal
save; do not reset product policy or overwrite unrelated state. Reopen the store
after normal save to distinguish fallback/cache from actual persistence. Keep
selected defaults validated against current user lists and retain unrelated
stored choices. This slice cannot acknowledge an authoritative preference write.

Reuse already-covered cases and add missing failure/retry compositions. Fix
demonstrated product defects while retaining atomic writes, writer locking,
actual persistence guarantees and cancellation. These are host/component
assertions, not native authentication or installed full-disk acceptance.

## Validation and close-out

Run affected unit and private-D-Bus component selections when crossing that
boundary. Retain exact expected/actual state and bounded privacy canaries;
review resource inventories for changed fixtures. Build after product edits,
update the owning state/diagnostic contract if necessary and record passing
checks in the queue before advancing to installed diagnostic recovery.
