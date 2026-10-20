# R06 — Recover owned kiosk infrastructure

Acceptance: host

Requires R05. Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject),
accepted lifecycle design and full manager/admission/recovery callers. Follow
the [lifecycle owner](../SystemDesign/Lifecycle.md#retained-material-activation-and-recovery),
[cleanup safety](../../tests/README.md#cleanup-safety-prerequisites) and applicable
test resource/storage contracts.

## Deliverable

Implement declared bounded waits/retries for transient startup dependencies and
one safe renewal of stale/failed owned kiosk infrastructure. Healthy reuse is
optional. A completed previous visit, unrelated host change or cosmetic update
must not force reboot or grow an unbounded collection of generations.

Use public service/session identities and existing admission serialization.
Preserve active kiosk visits, foreign sessions, replacement identities and
ordinary user managers. Never kill by blanket UID, guess a PID, reset global
logind settings or overwrite ambiguous state. Initialize only proven new owned
objects and preserve caller credentials.

Define fresh, preparing, ready, in-use, failed and recovering transitions with
one owner and observable outcomes. Recovery must survive interruption without
forgetting ownership or the first failure. A normal competing login follows the
accepted wait/attach/conflict contract, not a generic integrity rejection.

## Validation and close-out

Use maintained host tests for repeated entry, stale/failed state, restart races,
one successful retry, exhausted recovery, interrupted cleanup, foreign/replaced
state and live-session preservation. Verify no infinite retry or descriptor/
state growth and no overly tight clean-VM timing assumption.

Require the master's product review, resource review and `make build` after final
packaged edits. Record the finite recovery budget and final selectors for R09.
Update lifecycle/diagnostic contracts as needed and complete owned cleanup;
actual GDM lifetime acceptance remains R10/R11.
