# U07 — Recover requests after a temporary service outage

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U06.
Estimate: 45–90 min; session exception: one broker outage/restoration/request history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read the kiosk's startup/account/request callbacks, broker registration and
[recovery limits](../SystemDesign/Lifecycle.md#compatibility-and-recovery-boundary).
Discover existing broker owner-loss/retry operations and tests before adding any.

Use one temporary broker unavailability before a request is submitted. Preserve
safe unavailable feedback, bounded retry/exit and the first sanitized cause.
After service restoration, a supported retry or fresh entry must give a usable
request without reinstalling or manual state deletion. Fix demonstrated coupling
only; no generic dependency supervisor, cross-service outage matrix or unrelated
diagnostic-export project.

Observe no grant during outage, restored genuine approval with intended time
access and no duplicate/replayed approval. Host controls cover late callbacks,
deadline/cancellation and uncertain request results as applicable. Do not retry
an approval or mutation whose result is unknown. Run affected checks, required
backend review/build and owned restoration; close only U07.
