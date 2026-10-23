# F23 — Integrate Fedora transfer qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F22

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Qualify F22's standalone `runner --qualify-transfer` through
`Qualification.execute`, `check_graphical_smoke` and `AssetTransfer.provision`.
Reuse its helper, selector and history; change only target gates and evidenced
Fedora differences. Read complete affected functions and necessary callers.
Keep preboot work limited to transport
prerequisites; reusable payload moves through shared SSH only after readiness.
Qualify F22's shared Smoke readiness step on Fedora; keep package/upgrade
transfer semantics separate from reusable runtime provisioning.
An installed app snapshot cannot substitute for this product-free envelope.
Keep serial aliases gated until their own tasks.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew Ubuntu proof
only where invalidated under the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).

## Acceptance and cleanup

Confirm F22's existing `check_fixture_transfer` binding lists Fedora before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_transfer
```

Exercise the real standalone transfer preparation once and independent harmless
native use. Prove product absence and no reusable preboot upload. Reuse F22/shared
uncertain-transfer recovery proof unless Fedora changes that boundary; do not
repeat the fault matrix for a target gate extension. Stop before graphical input.
No package installation, transfer UI or customer journey acceptance is required.
Complete shared qualification and the master's close-out.
