# 009 — Durable request-state failure and retry

Acceptance: host

## Purpose and route

Required tasks: 008.
Read the [master](../Reliability-Plan.md),
[state durability contract](../SystemDesign/State.md),
[frontend state ownership](../SystemDesign/Frontends.md),
`broker/oh_no_parent_control/preferences.py`, kiosk `selection_store.py`,
agent-locale callbacks and complete relevant existing host tests.

Extend canonical `test_preferences.py` and `test_request_time_estimate.py` owners;
use launcher-configured private filesystem fixtures, real writer/merge logic
and explicit narrow syscall/job doubles. No host disk exhaustion, permission
changes to shared paths or additional database is needed.

## Finite failures and expected results

Cover temporary write refusal, replacement failure and directory-flush failure,
each followed by an identical request retry and a changed-value retry. Assert
confirmed saved values survive, unconfirmed writes are never acknowledged as
durable, and a failed flush invalidates the successful-file-identity shortcut.
Reopen the store to distinguish in-process cache success from persistence.

For non-authoritative selector files, pair malformed JSON and unwritable storage
with the documented in-memory fallback, reviewed failure stage and later normal
save; do not reset product policy or overwrite unrelated state. For agent
preparation, cover failed speculative warm-up, required retry, superseding
language and close/late-reply order. A completed restart for the wrong request
must not authorize submission.

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
