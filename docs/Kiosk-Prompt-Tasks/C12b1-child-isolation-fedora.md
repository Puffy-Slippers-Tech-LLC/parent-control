# C12b1 — Qualify healthy-child isolation on Fedora

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: C12b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use C10's exact registered per-child isolation binding and candidate inputs on
Fedora. Apply the VM/UI/storage owners and maintained installed runner.

Make one child's integration unavailable using the finite mapped fixture.
Verify its required enforcement remains safe, while the healthy child can make
a request and receive genuine parent approval. Restore the affected child and
verify its public request path works with policy intact. Keep the complete
before/fault/healthy-child/restored-child/restoration chain in one history.

Record exact commands, public results, timeout and owned restoration. Product
repairs require review/build and affected full-history reruns; no missing result
may be replaced by host checks or engineering probes.
For shared repairs, rerun invalidated complete Ubuntu histories before closing
this row and retain unchanged valid evidence. No Fedora release qualification
is implied.
