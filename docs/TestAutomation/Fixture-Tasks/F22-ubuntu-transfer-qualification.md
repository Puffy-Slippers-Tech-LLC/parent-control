# F22 — Integrate Ubuntu transfer qualification

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F21

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate standalone `runner --qualify-transfer` through
`Qualification.execute`, `check_graphical_smoke` and `AssetTransfer.provision`.
Read complete affected functions and necessary bootstrap/asset callers. Keep preboot work limited to transport
prerequisites; reusable payload moves through shared SSH only after readiness.
Put the shared fixture-readiness step at Smoke's post-SSH boundary, before its
first ready reply, for reuse by serial callers. Preserve package/upgrade transfer
semantics separately from reusable runtime provisioning.
An installed app snapshot cannot substitute for this product-free envelope.
Keep serial aliases gated until their own tasks.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Keep platform-specific corrections in their shared owning adapter.

## Acceptance and cleanup

Register/list the planned `check_fixture_transfer` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_transfer
```

Exercise the real standalone transfer preparation once and independent harmless
native use. Prove product absence and no reusable preboot upload. Reuse shared
uncertain-transfer recovery/no-replay proof; add a focused host check for changed
ordering and a live failure only if this caller introduces a distinct recovery
boundary under the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).
Stop before graphical input. Do not run package installation, transfer UI or
customer journey acceptance.
Complete shared qualification and the master's close-out.
