# 011 — Require confirmed secure locking

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 001, 005.
Estimate: 30–60 minutes; acknowledgement histories on both targets.

Read the [master](../Broker-Expiry-Plan.md), design's lock completion decisions
and complete GNOME/logind request/completion call chains in the current product.
Extend system-282 with planned `lock-completion` parameters (unimplemented).
Discover the existing fault routes and implement any missing bounded injection
at the maintained engineering owner, with exact identity/restoration. Use the
real service boundary; keep
production free of fault hooks and avoid another lock implementation.

Vary one condition per finite attempt: delayed acknowledgement or missing reply.
Observe actual protected input independently of request
success, ScreenSaver or LockedHint. Delayed/missing replies are never sufficient
success evidence; a completed lock still needs its input witness.

Use the controlled reply boundary to establish delayed/missing acknowledgement;
do not approximate it with a sleep close to the product deadline. Reuse the
qualified shared protected-input sequence rather than another discovery pass.

Where a current retry owner exists, retry only within the declared budget and
after revalidating current child,
session and balance. Commit a legitimate renewal during one pending attempt to
prove stale retry cannot lock the now-entitled desktop. Preserve work and peer
continuity. Positive daily time remains usable after grant expiry/removal.
Test current request behavior first; future retry behavior remains an external
replacement gate, not a mock-based pass. Do not add product retry implementation here.

Use lowest-layer existing host assertions for deterministic order, then real
fault histories on both targets. Restore exact owned service/fault state and
report request delivery separately from completion and protection.

Task 011a owns unavailable action/provider replacement. Where current production
has no retry owner, observe current behavior without inventing it; new broker
retry/revalidation remains an external replacement gate in the master.
