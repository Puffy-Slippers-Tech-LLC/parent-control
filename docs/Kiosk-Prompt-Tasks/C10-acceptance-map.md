# C10 — Freeze the finite final acceptance map

Acceptance: host

Required tasks: C09f.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Reconcile C04 and each protection/recovery task's registered bindings in the
existing scenario recipes, block catalogue and installed-case owners. For each
C11/C12 family below, record candidate inputs, exact command/selector, finite
values, expected independent public results, timeout, prerequisite qualification,
restoration. These are future checks, not inherited passes. Trust completed
usability gates; C11/C12 may reuse their checks for unchanged behavior. Identify
affected complete histories only after concrete later changes.

Apply [simple product and tests](../Kiosk-Session-Confinement-New-Plan.md#simple-product-and-tests)
to this composition. Reuse existing bindings and representative inputs for each
distinct outcome; avoid new wrappers or matrices solely for a task label. Keep
shared guards at their owner and use the shortest reliable public journey while
preserving each required result and complete fault/recovery history.

Families are core journey/features; separate host-variation and optional-fallback
bindings; required-service/
healthy-child recovery with Parent diagnostic download; owned-state/update
lifecycle; standalone terminal/TTY; SSH; separate remaining exposed-action
and consumed-input bindings. Each fault/recovery/reentry history stays complete. Use one
ordinary-account positive for each remaining route; absent SSH service is no pass.

Preserve the [local desktop boundary](../SystemDesign/Kiosk-Confinement.md#local-desktop-boundary)
and apply the master's [confinement priority](../Kiosk-Session-Confinement-New-Plan.md#confinement-priority).
C11t/C12t own standalone terminal/TTY assertions. A concrete change affecting
desktop behavior requires scoped checks without inspecting old reports.
Remote-desktop testing remains excluded.

This is a composition/readiness audit, not a broad implementation task.
Missing implementation or provider qualification requires an explicit bounded
prerequisite before C10 with the required installed targets. Do not hide it in
final acceptance. Run host inventory/composition/link checks, inspect runner
listing and refresh coverage where required. Retain matching evidence and
identify all affected reruns; no installed acceptance is claimed.
