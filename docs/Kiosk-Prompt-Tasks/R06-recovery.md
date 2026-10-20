# R06 — Bind approval lifetime through recovery

Acceptance: host

Required tasks: R06a — infrastructure renewal; R06b — per-child broker readiness.
Estimate: 60–120 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject),
accepted lifecycle design and full manager/admission/recovery callers. Follow
the [lifecycle owner](../SystemDesign/Lifecycle.md#retained-material-activation-and-recovery),
[cleanup safety](../../tests/README.md#cleanup-safety-prerequisites) and applicable
test resource/storage contracts.

## Session boundary

R06a owns infrastructure transitions, retries and identity-safe cleanup; R06b
owns cross-account broker startup isolation. This remaining task binds approval/
agent/request lifetime to those delivered recovery interfaces and competing
visits. Reuse their maintained callables and valid evidence. The next section
describes cumulative guarantees, not additional implementations in this task.

## Cumulative prerequisite guarantees

Implement declared bounded waits/retries for transient startup dependencies and
one safe renewal of stale/failed owned kiosk infrastructure. Healthy reuse is
optional. A completed previous visit, unrelated host change or cosmetic update
must not force reboot or grow an unbounded collection of generations.

Implement R01's [broker readiness decision](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery)
through the complete startup/extension-refresh callers. An unavailable home or
extension for child A must not prevent a genuine approved request for healthy
child B. Isolate/recover the affected operation while preserving required
enforcement and an actionable diagnostic for A. Do not silently skip enforcement
or turn this repair into a general broker rewrite.

Use public service/session identities and existing admission serialization.
Preserve active kiosk visits, foreign sessions, replacement identities and
ordinary user managers. Never kill by blanket UID, guess a PID, reset global
logind settings or overwrite ambiguous state. Initialize only proven new owned
objects and preserve caller credentials.

Define fresh, preparing, ready, in-use, failed and recovering transitions with
one owner and observable outcomes. Recovery must survive interruption without
forgetting ownership or the first failure. A normal competing login follows the
accepted wait/attach/conflict contract, not a generic integrity rejection.

## Remaining deliverable

Use the original end-to-end budget through usable form/authentication readiness,
not a fresh timeout at each retry or unit activation. Implement R01's exact
request/agent/logind-session association through renewal and competing visits,
preserving pending-authentication cancellation and implementing the accepted
[approval/commit ordering](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime).
Do not attach another visit to a pending authentication prompt or let a completed
old authentication supply authority to the new visit.

## Validation and close-out

Reuse applicable R06a/R06b results and run affected composition regressions for
repeated entry, stale/failed state, restart races,
one successful retry, exhausted recovery, interrupted cleanup, foreign/replaced
state and live-session preservation. Verify no infinite retry or descriptor/
state growth and no overly tight clean-VM timing assumption. Cover a pending
approval followed by session switch/exit and reentry: the late result grants
nothing, while a fresh request from the new visit can succeed.
Exercise both sides of the chosen approval/commit boundary with a delayed usage
query after authentication and a switch/exit/reentry; observe the original
request's grant outcome independently of the displayed prompt.
Cover child A's unavailable home at broker startup, successful approval for B,
restoration/recovery of A and the separate genuine-global-failure control.

Require the master's product review, resource review and `make build` after final
packaged edits. Record the finite recovery budget and final selectors for R09.
Update lifecycle/diagnostic contracts as needed and complete owned cleanup;
actual GDM acceptance is allocated to R10c1–R10c3/R10c and the matching Fedora
rows: visits, approval ordering, cross-child readiness and transient dependencies.
Close only R06.
