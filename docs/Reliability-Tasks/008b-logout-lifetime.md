# 008b — Bounded kiosk logout fallback

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract deterministic exit/fallback lifetime coverage from 008. Read the
[frontend lifecycle](../SystemDesign/Frontends.md), `KioskLogout`, native service
callbacks and complete canonical logout/cleanup tests. Reuse existing process,
callback and fake-clock adapters rather than introducing another exit protocol.

Cover successful native logout, native service failure/timeout, bounded fallback
and late completion after cancellation/close. The original exit deadline remains
bounded; repeated callbacks cannot dispatch duplicate exit operations or rearm
owned timers. Verify preparation timers, app/report children and recorded exit
processes are released or accurately reported by their owning boundary. Signals
apply only to recorded owned identities; diagnostic failure cannot turn cleanup
into a recovery loop. Preserve native authentication and confinement policy.

## Acceptance and close-out

Run exact affected unit/UI logout and ownership/cleanup files through
`tools/run-tests`, preserving explicit timeouts. Assert fallback order, dispatch
counts, original deadline and final owned resources. Follow the host resource
review for any changed lifetime. Fix demonstrated lifecycle defects, build as
required and retain actual runner evidence/cleanup. Close only 008b; usable GDM
and cycle-by-cycle native resource observations still belong to 008.
