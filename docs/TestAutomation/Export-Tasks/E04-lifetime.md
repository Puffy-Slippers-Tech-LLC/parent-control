# E04 — Preserve referenced proof within budgets

Acceptance: host
Requires: E03

## Purpose and delivery

Implement [lifetime and capacity](../Export-Design.md#lifetime-capacity-and-reuse)
through shared storage/retention/publication under the
[master](../Export-Execution-Plan.md). Read the complete retention rotation,
publication commit/recovery, bundle planning/export and plan-locator recovery
paths, including their resource and cleanup inventories.
Use E01's complete retirement map: `Store.session()`/`prune()`, automatic
`Store.reconcile()` with `completed_guard`, `test_recovery.cleanup_host()` and
privileged recovery callers, publication commit/finish/recovery and explicit
discard. Preserve each caller's existing authority and ownership boundary.

Separate working required proof and accepted referenced proof from disposable
execution/export rotation. Bind dependencies to authoritative consumers, not
arbitrary paths discovered in Markdown. Carry exact required proof before source
retirement; publish and verify its locator before superseded generation cleanup.
Implement the frozen bounded segmentation/compaction strategy without multiplying
owner budgets. Count all simultaneous retained/staging/recovery payloads and
metadata under existing finite limits. Report projected capacity and the supported
release/archive route before destructive rotation; preserve proof on refusal.
Required proof releases only through explicit owner-authorized dependency release
or verified replacement retaining the required closure. Task completion alone
does not release evidence still required by an accepted reference. Preserve
explicit discard authorization and unknown resources.
Enforce required-dependency/durable-acknowledgement checks on automatic oversized
startup retirement as well as ordinary count/byte pruning. A failed, cancelled
or unacknowledged capture must leave its required original available. Continue
automatic retirement of unreferenced disposable evidence. Register changed
retention/storage dependencies with the master's restart guard in this task.

## Validation and close-out

Exercise more than three later runs/exports, suspended/unpublished consumers,
capacity limits, file-count limits, interrupted compaction/locator replacement,
changed identities and stale dependency catalogues in private fixture stores.
Run the design's [report-rotation history](../Export-Design.md#required-regression-histories)
through both ordinary pruning and the host/privileged startup-recovery dispatch
with simulated privilege/target protocols. Cover failed capture, pending durable
acknowledgement, insufficient capacity, suspended consumers and verified replacement;
include the stale-acknowledgement refusal from the same history through each
automatic retirement route, preserving the required original until a matching
durable copy is verified. Assert the successful control actually retires its original path;
also assert unreferenced oversized evidence still retires. Retain
`test_host_preflight_automatically_retires_oversized_completed_evidence` and
`test_privileged_preflight_retires_oversized_run_under_vm_leases`, extending their
coverage for required proof instead of disabling existing recovery behavior.
Assert exact retained bytes, no dangling required references, total budget
accounting and nondeletion of foreign/replaced resources. Run applicable retention,
storage, bundle and plan-evidence cleanup-safety selections before protected
operations. Update their existing owners and follow the master's close-out.
