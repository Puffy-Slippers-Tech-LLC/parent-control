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

## Frozen prerequisite insertion

E01b allocation: 210–285 min total, with 45–60 min for this consumer's cross-route
composition and original acceptance. Custody's 60–75 min and retirement's
60–90 min ranges retain indivisible whole-set prepare/permit/removal/recovery
and the shared nonnested lock protocol. Splitting individual deletion calls
would leave alternate retirement routes unguarded. Collection replacement is
independently deliverable and retains its own full crash/capacity checks.

When E04 is selected, before implementation insert exactly this contiguous block
immediately before E04, using the existing finite briefs:

Brief navigation: [E04p-custody](E04p-custody.md), [E04p-collections](E04p-collections.md), [E04p-retirement](E04p-retirement.md).
The literal rows below use queue-relative destinations; copy them unchanged.

```markdown
| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | E04p-custody | [Implement dependency and retirement custody](Export-Tasks/E04p-custody.md) | E03 | Implement authoritative consumer custody, reservations and whole-set retirement permit/recovery without lock inversion | 60–75 min |
| [ ] | E04p-collections | [Implement bounded collection replacement](Export-Tasks/E04p-collections.md) | E04p-custody | Deliver bounded segmented collection replacement and compaction with simultaneous physical and metadata capacity accounting | 45–60 min |
| [ ] | E04p-retirement | [Gate every existing retirement route](Export-Tasks/E04p-retirement.md) | E04p-collections | Apply dependency and verified replacement gates to every frozen retirement route while preserving existing authority and disposable cleanup | 60–90 min |
```

Exact E04 Requires before: `E03`; after: `E03, E04p-retirement`.
At insertion update this brief's top-level Requires to that same after field.
New briefs declare `Acceptance: host`, no Targets. Keep every original E04
assertion and Scope, including both privileged startup calls, failed/stale ack
and disposable oversized controls; prerequisite passes alone cannot close E04.
Use the [shared insertion route](../../Execution-Plans.md#execution-and-delegation)
and [frozen guards](../Export-Design.md#frozen-insertion-guard-review).
Preserve other queue rows, finish owned cleanup, point to E04p-custody and return
`prerequisite_required` or valid `continue` with exact unfinished consumer work.
Do not adopt checkpoints or execute prerequisites during insertion. On resumption
compose the complete capture-to-retirement history and all inherited assertions.
