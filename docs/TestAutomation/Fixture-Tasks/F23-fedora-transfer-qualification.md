# F23 — Integrate Fedora transfer qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F22

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate standalone `runner --qualify-transfer` through
`Qualification.execute`, `check_graphical_smoke` and `AssetTransfer.provision`.
Read the complete bootstrap/asset chain. Keep preboot work limited to transport
prerequisites; reusable payload moves through shared SSH only after readiness.
Qualify F22's shared Smoke readiness step on Fedora; keep package/upgrade
transfer semantics separate from reusable runtime provisioning.
An installed app snapshot cannot substitute for this product-free envelope.
Keep serial aliases gated until their own tasks.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Register/list the planned `check_fixture_transfer` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_transfer
```

Exercise the real standalone transfer preparation and independent harmless
native use. Prove product absence, no reusable preboot upload and fail-closed
uncertain transfer recovery without replay. Stop before graphical input.
Complete shared qualification and the master's close-out.
