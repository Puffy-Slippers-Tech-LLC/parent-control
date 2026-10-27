# U02 — Keep healthy children able to request time

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U01a.
Estimate: 45–90 min; session exception: unavailable-child, healthy-child and restored-child history.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read [lifecycle availability](../SystemDesign/Lifecycle.md#compatibility-and-recovery-boundary)
and complete broker startup, `refresh_enabled_extensions` and extension activation
callers in `broker/oh_no_parent_control/`. Discover their existing tests.

Repair global readiness coupling when one enabled child's home/integration is
unavailable. Keep that child's enforcement authoritative and its unavailability
explicit; do not hide the child, fabricate readiness or substitute empty policy.
Prefer isolating the failed operation at its current owner over a new scheduler.

Use one unavailable-child fixture with a healthy child. Observe usable kiosk
entry and genuine approval/time access for the healthy child, safe refusal for
only operations that require the unavailable integration. Do not block that
child's entire request path if its authoritative dependencies remain usable.
Then restore the dependency through a supported retry/startup path and
verify that child's request. Preserve original sanitized diagnostics. No general
multi-child, policy or app catalogue campaign. Run scoped regressions, independent
backend review/build and owned cleanup; close only U02.
